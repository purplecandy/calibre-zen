#!/bin/bash
# Build the Linux calibre-zen package by wrapping calibre's own release binary.
#
# Nothing is compiled. calibre's .txz for the release pinned in
# packaging/upstream.json is downloaded, checked against its published sha256
# and unpacked; this fork's src/ is placed beside the binary's resources/
# directory; launchers that set CALIBRE_DEVELOP_FROM are added so the frozen
# calibre runs the fork's Python instead of its own. Forms, icons and bytecode
# are compiled here, once, so the installed tree is never written to.
#
# Runs on Linux only: the precompile and smoke-test steps execute the
# downloaded binary, so the machine's architecture picks the asset.
#
# Usage:  packaging/linux/package.sh [x86_64|arm64]
#
# Environment:
#   CALIBRE_ZEN_UPSTREAM_CACHE  where downloads are kept   (.calibre-zen/upstream)
#   CALIBRE_ZEN_BUILD_DIR       staging area, wiped         (build/linux-<arch>)
#   CALIBRE_ZEN_DIST_DIR        where the .txz lands        (dist)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PIN="$REPO/packaging/upstream.json"

say() { printf '==> %s\n' "$*"; }
die() { printf 'package.sh: %s\n' "$*" >&2; exit 1; }

[ "$(uname -s)" = Linux ] || die "this script runs the Linux binary it packages; run it on Linux (or in a container)"
for t in python3 curl tar xz sha256sum git; do
    command -v "$t" >/dev/null || die "need $t"
done

ARCH="${1:-$(uname -m)}"
case "$ARCH" in
    x86_64|amd64) ARCH=x86_64 ;;
    aarch64|arm64) ARCH=arm64 ;;
    *) die "unsupported architecture '$ARCH' (x86_64 or arm64)" ;;
esac
KEY="linux-$ARCH"

# The pin: one version, one asset name, one digest.
read -r VERSION ASSET SHA UPSTREAM_REPO ARCHIVE MIRROR < <(python3 - "$PIN" "$KEY" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
a = d['assets'][sys.argv[2]]
print(d['version'], a['name'], a['sha256'], d['repo'], d['archive'], d['mirror'])
PY
)
say "calibre $VERSION for $ARCH, from $UPSTREAM_REPO"

src_ver=$(sed -n "s/^numeric_version = (\([0-9]*\), \([0-9]*\), \([0-9]*\))/\1.\2.\3/p" "$REPO/src/calibre/constants.py")
[ "$src_ver" = "$VERSION" ] || die "src/calibre/constants.py is calibre $src_ver but upstream.json pins $VERSION; they must match"
APPNAME=$(sed -n "s/^__appname__ = '\([^']*\)'/\1/p" "$REPO/src/calibre/constants.py")
[ -n "$APPNAME" ] || die "could not read __appname__ from src/calibre/constants.py"
ZEN_VERSION=$(sed -n "s/^zen_version = '\([^']*\)'/\1/p" "$REPO/src/calibre/constants.py")
[ -n "$ZEN_VERSION" ] || die "could not read zen_version from src/calibre/constants.py"
say "$APPNAME $ZEN_VERSION"

CACHE="${CALIBRE_ZEN_UPSTREAM_CACHE:-$REPO/.calibre-zen/upstream}"
BUILD="${CALIBRE_ZEN_BUILD_DIR:-$REPO/build/linux-$ARCH}"
DIST="${CALIBRE_ZEN_DIST_DIR:-$REPO/dist}"
STAGE="$BUILD/$APPNAME"
mkdir -p "$CACHE" "$DIST"

# ---------------------------------------------------------------- download
TARBALL="$CACHE/$ASSET"
if [ ! -f "$TARBALL" ]; then
    # Our mirror first (upstream-mirror.py keeps a copy of every release we
    # have seen), then upstream's own archive, which keeps every version,
    # then GitHub, which loses a release's assets when the next one ships.
    # The digest check below is what makes the order a matter of
    # availability only.
    for url in "https://github.com/$MIRROR/releases/download/upstream-$VERSION/$ASSET" \
               "$ARCHIVE/$VERSION/$ASSET" \
               "https://github.com/$UPSTREAM_REPO/releases/download/v$VERSION/$ASSET"; do
        say "downloading $url"
        if curl -fL --retry 3 -o "$TARBALL.part" "$url"; then break; fi
        rm -f "$TARBALL.part"
    done
    [ -f "$TARBALL.part" ] || die "could not download $ASSET from the mirror, the archive or GitHub"
    mv "$TARBALL.part" "$TARBALL"
fi
say "verifying sha256"
echo "$SHA  $TARBALL" | sha256sum -c --quiet - || die "$ASSET does not match the digest in upstream.json"

# ------------------------------------------------------------------ unpack
say "unpacking into $STAGE"
rm -rf "$BUILD"
mkdir -p "$STAGE"
tar -xJf "$TARBALL" -C "$STAGE"
[ -x "$STAGE/calibre-debug" ] || die "unexpected layout: no calibre-debug at the top of the tarball"
[ -d "$STAGE/resources" ] || die "unexpected layout: no resources/ at the top of the tarball"

# ------------------------------------------------------- the fork's Python
# Beside resources/, because develop mode looks for resources at
# <CALIBRE_DEVELOP_FROM>/../resources. Putting src here makes that the
# binary's own, complete resources directory. Nothing is duplicated.
say "adding src/"
tar -C "$REPO" --exclude='__pycache__' --exclude='*.pyc' --exclude='*_ui.py' -cf - src | tar -C "$STAGE" -xf -

# The fork's changed resource files (icons), laid over the binary's. Only what
# differs from the upstream tag, so the tag has to be present.
if ! git -C "$REPO" rev-parse -q --verify "refs/tags/v$VERSION" >/dev/null; then
    say "fetching tag v$VERSION from $UPSTREAM_REPO"
    git -C "$REPO" fetch --depth=1 "https://github.com/$UPSTREAM_REPO.git" "tag" "v$VERSION"
fi
say "adding the fork's resource files"
git -C "$REPO" diff --name-only --diff-filter=AM "v$VERSION" -- resources | while read -r f; do
    echo "    $f"
    mkdir -p "$STAGE/$(dirname "$f")"
    cp "$REPO/$f" "$STAGE/$f"
done

# --------------------------------------------------------------- launchers
# One per public launcher at the top of the tarball. Inside the tree the
# upstream names stay, because calibre spawns its helpers by basename; what a
# user runs is prefixed, following calibre.linux.path_name(). calibre-parallel
# is internal and inherits the environment from whatever spawned it.
say "writing launchers"
mkdir -p "$STAGE/zen-bin"
wrap() { # $1 = upstream launcher name, $2 = wrapper path
    cat > "$2" <<EOF
#!/bin/sh
# $APPNAME: run calibre's frozen '$1' on this fork's Python.
here=\$(cd "\$(dirname "\$(readlink -f "\$0")")/.." && pwd)
export CALIBRE_DEVELOP_FROM="\$here/src"
export CALIBRE_ZEN_PACKAGED=1
exec "\$here/$1" "\$@"
EOF
    chmod 755 "$2"
}
for exe in "$STAGE"/*; do
    [ -f "$exe" ] && [ -x "$exe" ] || continue
    name=$(basename "$exe")
    [ "$name" = calibre-parallel ] && continue
    wrap "$name" "$STAGE/zen-bin/zen-$name"
done
# The GUI, under the application's own name, at the top where people look.
wrap calibre "$STAGE/zen-bin/$APPNAME"
sed "s#\")/..\"#\")\"#" "$STAGE/zen-bin/$APPNAME" > "$STAGE/$APPNAME" # here = the top dir itself
chmod 755 "$STAGE/$APPNAME"

# -------------------------------------------------------------- precompile
# Everything develop mode would otherwise build at first launch, done now,
# with the bundle's own Python so the bytecode matches its interpreter.
export TZ="${TZ:-Etc/UTC}"
WORK_CONFIG=$(mktemp -d)
trap 'rm -rf "$WORK_CONFIG"' EXIT
run_in_stage() { # runs calibre-debug from the stage, in develop mode, config kept out of $HOME
    env CALIBRE_DEVELOP_FROM="$STAGE/src" CALIBRE_CONFIG_DIRECTORY="$WORK_CONFIG" \
        QT_QPA_PLATFORM=offscreen "$@"
}
say "compiling UI forms and icons.rcc"
CALIBRE_FORCE_BUILD_UI_FORMS=1 run_in_stage "$STAGE/calibre-debug" -c '
import os
from calibre.build_forms import build_forms
build_forms(os.environ["CALIBRE_DEVELOP_FROM"], summary=True)
'
say "compiling bytecode"
run_in_stage "$STAGE/calibre-debug" -c '
import compileall, os, sys
ok = compileall.compile_dir(os.environ["CALIBRE_DEVELOP_FROM"], quiet=1, workers=0)
sys.exit(0 if ok else 1)
'

# ------------------------------------------------------------------- smoke
say "smoke test: identity"
MARK=$(mktemp)
CALIBRE_CONFIG_DIRECTORY="$WORK_CONFIG" "$STAGE/zen-bin/zen-calibre-debug" -c "
from calibre.constants import __appname__, numeric_version, config_dir, is_running_from_develop
# The bundle runs Python with -OO, which strips assert statements, so a
# check has to be an if. No quotes in here: this text sits inside shell
# strings of both kinds.
def check(ok, msg):
    if not ok:
        raise SystemExit(msg)
import calibre, calibre_zen
check(__appname__ == '$APPNAME', __appname__)
check('.'.join(map(str, numeric_version)) == '$VERSION', numeric_version)
check(not is_running_from_develop, 'develop mode is still on: the package would rebuild itself at launch')
check(calibre.__file__.startswith('$STAGE/src/'), calibre.__file__)
print('    appname   ', __appname__)
print('    version   ', '.'.join(map(str, numeric_version)))
print('    python    ', calibre.__file__)
print('    overlay   ', calibre_zen.__file__)
print('    config dir', config_dir)
" || die "identity check failed"

say "smoke test: headless GUI with the overlay"
CALIBRE_CONFIG_DIRECTORY="$WORK_CONFIG" QT_QPA_PLATFORM=offscreen "$STAGE/zen-bin/zen-calibre-debug" -c '
from calibre.gui2 import Application
# The bundle runs Python with -OO, which strips assert statements, so a
# check has to be an if. No quotes in here: this text sits inside shell
# strings of both kinds.
def check(ok, msg):
    if not ok:
        raise SystemExit(msg)
app = Application([], force_calibre_style=True)
n = len(app.styleSheet())
check(n > 1000, f"overlay sheet is only {n} bytes")
print("    style sheet", n, "bytes")
' || die "headless GUI check failed"

written=$(find "$STAGE" -newer "$MARK" -print)
rm -f "$MARK"
if [ -n "$written" ]; then
    printf '%s\n' "$written" | sed 's/^/    /' >&2
    die "the package wrote into itself at launch (above); it must not, it may be installed read-only"
fi

# --------------------------------------------------------------------- tar
OUT="$DIST/$APPNAME-$ZEN_VERSION-linux-$ARCH.txz"
say "packing $OUT"
rm -f "$OUT"
XZ_OPT="${XZ_OPT:--T0 -6}" tar -C "$BUILD" --owner=0 --group=0 --numeric-owner -cJf "$OUT" "$APPNAME"
# A bare file name in the checksum file, so `sha256sum -c` works wherever the
# two files are put, and the release feed can read the name back.
(cd "$DIST" && sha256sum "$(basename "$OUT")" > "$(basename "$OUT").sha256")
say "done: $(du -h "$OUT" | cut -f1) $OUT"
