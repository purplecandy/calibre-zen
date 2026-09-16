#!/bin/sh
# Build a standalone calibre-zen.app you can actually run, by re-wrapping an
# installed calibre.app.
#
# This is a PREVIEW build, not the real one. BUILDING.md describes the real
# pipeline (bypy, dependencies compiled from source, a signed .dmg); this
# produces something to try today, on one machine, without any of that.
#
# What it is: a copy of the installed calibre bundle, with the overlay added,
# its identity replaced, and its own icon. It is self-contained -- it carries
# its own Qt, Python and calibre -- so it runs whether or not calibre is still
# installed, and it runs beside calibre without touching its settings.
#
# What it is not: built from this fork's own src/calibre. A built calibre has
# no Python source in it (freeze_python compiles every module into
# calibre-launcher.dylib), so the frozen calibre inside the copy is upstream's,
# and packaging/macos/bootstrap.py re-establishes the fork's identity at
# runtime. The checks below make sure the two say the same thing.
#
# Usage:  packaging/macos/build-preview.sh [output-dir]
set -e

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
SRC_APP="${CALIBRE_ZEN_BUNDLE:-/Applications/calibre.app}"
OUT="${1:-$REPO/dist}"
BOOT="$REPO/packaging/macos/bootstrap.py"

die() { echo "build-preview: $*" >&2; exit 1; }

[ -d "$SRC_APP" ] || die "no calibre.app at $SRC_APP (set CALIBRE_ZEN_BUNDLE)"

# The overlay wraps calibre's own classes by name, so it is only valid against
# the version it was written for. A preview built on a mismatched bundle would
# fail somewhere deep instead of here.
src_ver=$(sed -n "s/^numeric_version = (\([0-9]*\), \([0-9]*\), \([0-9]*\))/\1.\2.\3/p" "$REPO/src/calibre/constants.py")
app_ver=$("$SRC_APP/Contents/MacOS/calibre-debug" --version 2>/dev/null | sed -n 's/.*calibre \([0-9.]*\).*/\1/p')
case "$src_ver" in
    "$app_ver"|"$app_ver".0) ;;
    *) die "source is calibre $src_ver but $SRC_APP is $app_ver; update one of them" ;;
esac

# The fork's name, read from the source rather than repeated here.
APPNAME=$(sed -n "s/^__appname__ = '\([^']*\)'/\1/p" "$REPO/src/calibre/constants.py")
[ -n "$APPNAME" ] || die "could not read __appname__ from src/calibre/constants.py"

# bootstrap.py restates that name because it runs against a stock frozen
# calibre. If the two ever drift, the preview would keep calibre's identity and
# quietly share its config and its single-instance lock.
boot_name=$(sed -n "s/^APPNAME = '\([^']*\)'/\1/p" "$BOOT")
[ "$boot_name" = "$APPNAME" ] || die "bootstrap.py says '$boot_name', constants.py says '$APPNAME'"

APP="$OUT/$APPNAME.app"
C="$APP/Contents"

echo "building $APPNAME $src_ver"
echo "  from   $SRC_APP"
echo "  into   $APP"

rm -rf "$APP"
mkdir -p "$OUT"
echo "  copying the bundle (about 1.1GB)..."
ditto "$SRC_APP" "$APP"

# The copy's seal covers the Info.plist and the resource list, both of which
# change below, so it is removed and a fresh ad-hoc signature applied at the
# end. Nested code keeps its original signatures and is not re-signed.
rm -rf "$C/_CodeSignature" "$C/CodeResources"

echo "  adding the overlay"
rm -rf "$C/Resources/zen"
mkdir -p "$C/Resources/zen"
ditto --norsrc --noextattr "$REPO/src/calibre_zen" "$C/Resources/zen/calibre_zen"
find "$C/Resources/zen" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
cp "$BOOT" "$C/Resources/zen/bootstrap.py"

echo "  writing the launcher"
cat > "$C/MacOS/$APPNAME" <<LAUNCHER
#!/bin/sh
# calibre.constants computes config_dir at import time, before any Python of
# ours can run, so this is the one piece of the fork's identity that has to be
# an environment variable rather than a patch.
DIR=\$(cd "\$(dirname "\$0")" && pwd)
: "\${CALIBRE_CONFIG_DIRECTORY:=\$HOME/Library/Preferences/$APPNAME}"
export CALIBRE_CONFIG_DIRECTORY
mkdir -p "\$CALIBRE_CONFIG_DIRECTORY"
exec "\$DIR/calibre-debug" -e "\$DIR/../Resources/zen/bootstrap.py" -- "\$@"
LAUNCHER
chmod +x "$C/MacOS/$APPNAME"

echo "  rendering the icon"
ICONSET="$OUT/$APPNAME.iconset"
rm -rf "$ICONSET"
"$SRC_APP/Contents/MacOS/calibre-debug" -e "$REPO/packaging/macos/render_icon.py" -- \
    "$REPO/imgsrc/calibre.svg" "$ICONSET" >/dev/null
iconutil -c icns "$ICONSET" -o "$C/Resources/$APPNAME.icns"
rm -rf "$ICONSET"

echo "  rewriting Info.plist"
PL="$C/Info.plist"
plutil -replace CFBundleName            -string "$APPNAME"    "$PL"
plutil -replace CFBundleDisplayName     -string "$APPNAME"    "$PL"
plutil -replace CFBundleExecutable      -string "$APPNAME"    "$PL"
plutil -replace CFBundleIdentifier      -string "io.github.purplecandy.$APPNAME" "$PL"
plutil -replace CFBundleIconFile        -string "$APPNAME.icns" "$PL"
# CFBundleIconName points into Assets.car, which we cannot rebuild without
# Xcode; left in place it would win and the Dock would show calibre's icon.
plutil -remove CFBundleIconName "$PL" 2>/dev/null || true
plutil -replace CFBundleURLTypes -json "[{\"CFBundleTypeRole\":\"Viewer\",\"CFBundleURLName\":\"io.github.purplecandy.$APPNAME-url\",\"CFBundleURLSchemes\":[\"$APPNAME\"]}]" "$PL"
plutil -replace NSHumanReadableCopyright -string "Copyright Kovid Goyal; $APPNAME fork copyright Nadeem Siddique" "$PL"

# --deep, because the main executable's own signature embeds a hash of the
# bundle's Info.plist: rewriting the plist invalidates Contents/MacOS/calibre
# as well as the outer seal, and signing only the outer one leaves a bundle
# that will not verify. Piping to sed would swallow codesign's exit status, so
# the output is captured instead.
echo "  signing (ad-hoc)"
if ! out=$(codesign --force --deep --sign - "$APP" 2>&1); then
    echo "$out" | sed 's/^/    /'
    die "codesign failed"
fi
if ! out=$(codesign --verify --deep --strict --verbose=1 "$APP" 2>&1); then
    echo "$out" | sed 's/^/    /'
    die "signature does not verify"
fi
echo "$out" | sed 's/^/    /'

echo
echo "built: $APP"
du -sh "$APP" | sed 's/^/size:  /'
echo
echo "It is ad-hoc signed, not notarized. Running it from here is fine."
echo "If you copy it to another Mac, macOS will quarantine it and Gatekeeper"
echo "will refuse a double-click -- right-click -> Open, once, to get past that."
