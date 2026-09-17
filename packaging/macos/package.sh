#!/bin/bash
# Build calibre-zen.app and its .dmg by wrapping calibre's own release bundle.
#
# Nothing is compiled. calibre's .dmg for the release pinned in
# packaging/upstream.json is downloaded, checked against its published sha256
# and mounted; calibre.app is copied out; this fork's src/ goes beside the
# bundle's resources/ directory; a launcher that sets CALIBRE_DEVELOP_FROM
# becomes the bundle's executable, so the frozen calibre runs the fork's Python
# instead of its own. The bundle's identity, icon and signature are replaced.
# Forms, icons and bytecode are compiled here, once, so the installed bundle is
# never written to -- which matters on macOS, where Gatekeeper may run a
# downloaded app from a read-only translocated mount.
#
# Runs on macOS only. Unsigned by default (ad hoc: right-click -> Open once on
# another Mac); with a Developer ID in the environment it is signed, and with
# CALIBRE_ZEN_NOTARIZE=1 notarized and stapled as well -- see sign.py for the
# variables. CI supplies them from repository secrets; a checkout without them
# still builds, unsigned.
#
# Usage:  packaging/macos/package.sh
#
# Environment:
#   CALIBRE_ZEN_SIGN_IDENTITY   Developer ID Application common name; sign.py
#   CALIBRE_ZEN_NOTARIZE=1      documents the rest (certificate, notary key)
#   CALIBRE_ZEN_UPSTREAM_CACHE  where downloads are kept   (.calibre-zen/upstream)
#   CALIBRE_ZEN_BUILD_DIR       staging area, wiped         (build/macos)
#   CALIBRE_ZEN_DIST_DIR        where the .dmg lands        (dist)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
HERE="$REPO/packaging/macos"
PIN="$REPO/packaging/upstream.json"

say() { printf '==> %s\n' "$*"; }
die() { printf 'package.sh: %s\n' "$*" >&2; exit 1; }

[ "$(uname -s)" = Darwin ] || die "this script runs the macOS bundle it packages; run it on macOS"
for t in python3 curl hdiutil ditto plutil codesign iconutil shasum git; do
    command -v "$t" >/dev/null || die "need $t"
done

read -r VERSION ASSET SHA UPSTREAM_REPO < <(python3 - "$PIN" macos <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
a = d['assets'][sys.argv[2]]
print(d['version'], a['name'], a['sha256'], d['repo'])
PY
)
say "calibre $VERSION for macOS, from $UPSTREAM_REPO"

src_ver=$(sed -n "s/^numeric_version = (\([0-9]*\), \([0-9]*\), \([0-9]*\))/\1.\2.\3/p" "$REPO/src/calibre/constants.py")
[ "$src_ver" = "$VERSION" ] || die "src/calibre/constants.py is calibre $src_ver but upstream.json pins $VERSION; they must match"
APPNAME=$(sed -n "s/^__appname__ = '\([^']*\)'/\1/p" "$REPO/src/calibre/constants.py")
[ -n "$APPNAME" ] || die "could not read __appname__ from src/calibre/constants.py"
ZEN_VERSION=$(sed -n "s/^zen_version = '\([^']*\)'/\1/p" "$REPO/src/calibre/constants.py")
[ -n "$ZEN_VERSION" ] || die "could not read zen_version from src/calibre/constants.py"
DISPLAY_NAME=$(sed -n "s/^zen_display_name = '\([^']*\)'/\1/p" "$REPO/src/calibre/constants.py")
[ -n "$DISPLAY_NAME" ] || die "could not read zen_display_name from src/calibre/constants.py"
say "$DISPLAY_NAME $ZEN_VERSION ($APPNAME)"
BUNDLE_ID="io.github.purplecandy.$APPNAME"

CACHE="${CALIBRE_ZEN_UPSTREAM_CACHE:-$REPO/.calibre-zen/upstream}"
BUILD="${CALIBRE_ZEN_BUILD_DIR:-$REPO/build/macos}"
DIST="${CALIBRE_ZEN_DIST_DIR:-$REPO/dist}"
# The bundle is named as a person sees it; the executable inside keeps the
# identity name, so the process is still calibre-zen.
APP="$BUILD/$DISPLAY_NAME.app"
C="$APP/Contents"
mkdir -p "$CACHE" "$DIST"

# ---------------------------------------------------------------- download
DMG="$CACHE/$ASSET"
if [ ! -f "$DMG" ]; then
    say "downloading $ASSET"
    curl -fL --retry 3 -o "$DMG.part" \
        "https://github.com/$UPSTREAM_REPO/releases/download/v$VERSION/$ASSET"
    mv "$DMG.part" "$DMG"
fi
say "verifying sha256"
echo "$SHA  $DMG" | shasum -a 256 -c --status - || die "$ASSET does not match the digest in upstream.json"

# ------------------------------------------------------------- copy it out
say "copying calibre.app out of the image"
rm -rf "$BUILD"
mkdir -p "$BUILD"
MNT=$(mktemp -d)
hdiutil attach -nobrowse -readonly -quiet -mountpoint "$MNT" "$DMG"
trap 'hdiutil detach -quiet "$MNT" 2>/dev/null || true' EXIT
[ -d "$MNT/calibre.app" ] || die "no calibre.app in $ASSET"
ditto "$MNT/calibre.app" "$APP"
hdiutil detach -quiet "$MNT"
trap - EXIT
[ -x "$C/MacOS/calibre-debug" ] || die "unexpected layout: no Contents/MacOS/calibre-debug"
[ -d "$C/Resources/resources" ] || die "unexpected layout: no Contents/Resources/resources"

# The copy's seal covers Info.plist and the resource list, both of which
# change below; a fresh signature is applied at the end.
rm -rf "$C/_CodeSignature" "$C/CodeResources"

# ------------------------------------------------------- the fork's Python
# Beside Contents/Resources/resources, because develop mode looks for
# resources at <CALIBRE_DEVELOP_FROM>/../resources. Nothing is duplicated.
say "adding src/"
tar -C "$REPO" --exclude='__pycache__' --exclude='*.pyc' --exclude='*_ui.py' -cf - src | tar -C "$C/Resources" -xf -
find "$C/Resources/src" -name '.DS_Store' -delete

if ! git -C "$REPO" rev-parse -q --verify "refs/tags/v$VERSION" >/dev/null; then
    say "fetching tag v$VERSION from $UPSTREAM_REPO"
    git -C "$REPO" fetch --depth=1 "https://github.com/$UPSTREAM_REPO.git" "tag" "v$VERSION"
fi
say "adding the fork's resource files"
git -C "$REPO" diff --name-only --diff-filter=AM "v$VERSION" -- resources | while read -r f; do
    echo "    $f"
    dest="$C/Resources/${f}" # resources/... lands in Contents/Resources/resources/...
    mkdir -p "$(dirname "$dest")"
    cp "$REPO/$f" "$dest"
done

# ---------------------------------------------------------------- launcher
# The bundle's executable becomes a script that points the frozen calibre at
# the fork's source and starts the GUI. Everything calibre spawns from there
# (workers, the viewer and editor bundles) inherits the environment.
say "writing the launcher"
cat > "$C/MacOS/$APPNAME" <<LAUNCHER
#!/bin/sh
# $APPNAME: calibre's frozen binary, running this fork's Python.
DIR=\$(cd "\$(dirname "\$0")" && pwd)
export CALIBRE_DEVELOP_FROM="\$DIR/../Resources/src"
export CALIBRE_ZEN_PACKAGED=1
exec "\$DIR/calibre" "\$@"
LAUNCHER
chmod 755 "$C/MacOS/$APPNAME"

# -------------------------------------------------------------- precompile
export TZ="${TZ:-Etc/UTC}"
WORK_CONFIG=$(mktemp -d)
trap 'rm -rf "$WORK_CONFIG"' EXIT
run_in_stage() {
    env CALIBRE_DEVELOP_FROM="$C/Resources/src" CALIBRE_CONFIG_DIRECTORY="$WORK_CONFIG" \
        QT_QPA_PLATFORM=offscreen "$@"
}
say "compiling UI forms and icons.rcc"
CALIBRE_FORCE_BUILD_UI_FORMS=1 run_in_stage "$C/MacOS/calibre-debug" -c '
import os
from calibre.build_forms import build_forms
build_forms(os.environ["CALIBRE_DEVELOP_FROM"], summary=True)
'
say "compiling bytecode"
run_in_stage "$C/MacOS/calibre-debug" -c '
import compileall, os, sys
ok = compileall.compile_dir(os.environ["CALIBRE_DEVELOP_FROM"], quiet=1, workers=0)
sys.exit(0 if ok else 1)
'

# --------------------------------------------------------- icon and plist
say "rendering the icon"
ICONSET="$BUILD/$APPNAME.iconset"
rm -rf "$ICONSET"
"$C/MacOS/calibre-debug" -e "$HERE/render_icon.py" -- "$REPO/imgsrc/calibre.svg" "$ICONSET" >/dev/null
iconutil -c icns "$ICONSET" -o "$C/Resources/$APPNAME.icns"
rm -rf "$ICONSET"

say "rewriting Info.plist"
PL="$C/Info.plist"
plutil -replace CFBundleName        -string "$DISPLAY_NAME" "$PL"
plutil -replace CFBundleDisplayName -string "$DISPLAY_NAME" "$PL"
plutil -replace CFBundleExecutable  -string "$APPNAME" "$PL"
plutil -replace CFBundleIdentifier  -string "$BUNDLE_ID" "$PL"
plutil -replace CFBundleIconFile    -string "$APPNAME.icns" "$PL"
# The fork's version is the bundle's; the calibre it is built on is stated
# where Finder's Get Info shows it.
plutil -replace CFBundleShortVersionString -string "$ZEN_VERSION" "$PL"
plutil -replace CFBundleVersion            -string "$ZEN_VERSION" "$PL"
# CFBundleIconName points into Assets.car, which cannot be rebuilt without
# Xcode; left in place it wins and the Dock shows calibre's icon.
plutil -remove CFBundleIconName "$PL" 2>/dev/null || true
plutil -replace CFBundleURLTypes -json "[{\"CFBundleTypeRole\":\"Viewer\",\"CFBundleURLName\":\"$BUNDLE_ID-url\",\"CFBundleURLSchemes\":[\"$APPNAME\"]}]" "$PL"
plutil -replace NSHumanReadableCopyright -string "$APPNAME $ZEN_VERSION on calibre $VERSION. Copyright Kovid Goyal; $APPNAME fork copyright Nadeem Siddique" "$PL"

# -------------------------------------------------------------------- sign
# With CALIBRE_ZEN_SIGN_IDENTITY set, sign.py signs inside-out with the
# Developer ID, hardened runtime and entitlements, and with CALIBRE_ZEN_NOTARIZE=1
# also submits the bundle to Apple and staples the ticket -- to the bundle, so
# it survives being dragged out of the image. Without an identity the bundle is
# signed ad hoc: --deep, because the main executable's signature seals a hash of
# Info.plist, so rewriting the plist invalidates it too. Ad hoc means Gatekeeper
# refuses the first double-click; right-click -> Open gets past it.
NOTARIZE_FLAG=""
[ "${CALIBRE_ZEN_NOTARIZE:-0}" = 1 ] && NOTARIZE_FLAG="--notarize"
if [ -n "${CALIBRE_ZEN_SIGN_IDENTITY:-}" ]; then
    say "signing with $CALIBRE_ZEN_SIGN_IDENTITY${NOTARIZE_FLAG:+, then notarizing}"
    # shellcheck disable=SC2086
    python3 "$HERE/sign.py" "$APP" $NOTARIZE_FLAG || die "signing failed"
else
    say "signing (ad hoc)"
    if ! out=$(codesign --force --deep --sign - "$APP" 2>&1); then
        printf '%s\n' "$out" | sed 's/^/    /' >&2
        die "codesign failed"
    fi
fi
if ! out=$(codesign --verify --deep --strict --verbose=1 "$APP" 2>&1); then
    printf '%s\n' "$out" | sed 's/^/    /' >&2
    die "signature does not verify"
fi

# ------------------------------------------------------------------- smoke
# After signing, so what is tested is what ships.
say "smoke test: identity"
MARK=$(mktemp)
env CALIBRE_DEVELOP_FROM="$C/Resources/src" CALIBRE_ZEN_PACKAGED=1 CALIBRE_CONFIG_DIRECTORY="$WORK_CONFIG" \
    "$C/MacOS/calibre-debug" -c "
from calibre.constants import __appname__, numeric_version, config_dir, is_running_from_develop
# The bundle runs Python with -OO, which strips assert statements, so a
# check has to be an if. No quotes in here: this text sits inside shell
# strings of both kinds.
def check(ok, msg):
    if not ok:
        raise SystemExit(msg)
from calibre.utils.ipc import gui_socket_address
from calibre.utils.lock import singleinstance_path
import calibre, calibre_zen
check(__appname__ == '$APPNAME', __appname__)
check('.'.join(map(str, numeric_version)) == '$VERSION', numeric_version)
check(not is_running_from_develop, 'develop mode is still on: the bundle would rebuild itself at launch')
check(calibre.__file__.startswith('$C/Resources/src/'), calibre.__file__)
print('    appname   ', __appname__)
print('    version   ', '.'.join(map(str, numeric_version)))
print('    python    ', calibre.__file__)
print('    overlay   ', calibre_zen.__file__)
print('    lock      ', singleinstance_path('GUI'))
print('    gui socket', gui_socket_address())
" || die "identity check failed"

say "smoke test: headless GUI with the overlay"
env CALIBRE_DEVELOP_FROM="$C/Resources/src" CALIBRE_ZEN_PACKAGED=1 CALIBRE_CONFIG_DIRECTORY="$WORK_CONFIG" \
    QT_QPA_PLATFORM=offscreen "$C/MacOS/calibre-debug" -c '
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

written=$(find "$APP" -newer "$MARK" -print)
rm -f "$MARK"
if [ -n "$written" ]; then
    printf '%s\n' "$written" | sed 's/^/    /' >&2
    die "the bundle wrote into itself at launch (above); it must not"
fi
codesign --verify --deep --strict "$APP" || die "signature no longer verifies after the smoke test"

# --------------------------------------------------------------------- dmg
# A .zip unpacked by Archive Utility can lose the symlinks the frameworks
# depend on and the extended attributes the signature is sealed against; a
# disk image carries both intact.
OUT="$DIST/$APPNAME-$ZEN_VERSION-macos.dmg"
say "building $OUT"
STAGE="$BUILD/dmg"
rm -rf "$STAGE" "$OUT"
mkdir -p "$STAGE"
ditto "$APP" "$STAGE/$DISPLAY_NAME.app"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "$DISPLAY_NAME" -srcfolder "$STAGE" -fs HFS+ -format ULFO -quiet -ov "$OUT"
rm -rf "$STAGE"
if [ -n "${CALIBRE_ZEN_SIGN_IDENTITY:-}" ]; then
    # The image gets its own signature and ticket. The app's ticket is what
    # lets a first launch work offline once dragged out; the image's is what
    # lets a quarantined download be mounted at all.
    say "signing the image${NOTARIZE_FLAG:+, then notarizing}"
    # shellcheck disable=SC2086
    python3 "$HERE/sign.py" "$OUT" $NOTARIZE_FLAG || die "signing the image failed"
fi
shasum -a 256 "$OUT" > "$OUT.sha256"
say "done: $(du -h "$OUT" | cut -f1) $OUT"
if [ -z "${CALIBRE_ZEN_SIGN_IDENTITY:-}" ]; then
    echo "    ad hoc signed, not notarized: on another Mac, right-click -> Open once."
elif [ -z "$NOTARIZE_FLAG" ]; then
    echo "    signed but not notarized: Gatekeeper still refuses a download. Set CALIBRE_ZEN_NOTARIZE=1."
else
    echo "    signed, notarized and stapled: opens on a Mac that has never seen it."
fi
