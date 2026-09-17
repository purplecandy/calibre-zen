#!/bin/bash
# Re-sign dist/calibre-zen.app ad hoc and wrap it in a compressed DMG.
#
# A DMG is the right way to hand this bundle to someone else. A .zip unpacked
# by Archive Utility can lose the symlinks the frameworks depend on and the
# extended attributes the signature is sealed against, and the app then refuses
# to open on the other machine; a disk image is a filesystem, so it carries
# both intact.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
APP="$REPO/dist/calibre-zen.app"
DMG="$REPO/dist/calibre-zen-macos.dmg"
STAGE="$REPO/dist/.dmg-stage"

die() { echo "make-dmg: $*" >&2; exit 1; }

[ -d "$APP" ] || die "no app at $APP -- run build-preview.sh first"

echo "==> re-signing"
# --deep because the main executable's signature seals a hash of the bundle's
# Info.plist, which build-preview.sh edits.
out=$(codesign --force --deep --sign - "$APP" 2>&1) || die "codesign failed: $out"
codesign --verify --deep --strict "$APP" || die "signature does not verify"
codesign -dv "$APP" 2>&1 | grep -E 'Identifier|Signature'

echo "==> staging"
rm -rf "$STAGE" "$DMG"
mkdir -p "$STAGE"
ditto "$APP" "$STAGE/calibre-zen.app"
ln -s /Applications "$STAGE/Applications"

echo "==> building the image"
hdiutil create \
    -volname "calibre-zen" \
    -srcfolder "$STAGE" \
    -fs HFS+ \
    -format ULFO \
    -ov "$DMG" >/dev/null
rm -rf "$STAGE"

echo "==> verifying the image"
hdiutil verify "$DMG" >/dev/null || die "image does not verify"
mount=$(mktemp -d)
hdiutil attach "$DMG" -nobrowse -readonly -mountpoint "$mount" >/dev/null
codesign --verify --deep --strict "$mount/calibre-zen.app" || { hdiutil detach "$mount" >/dev/null; die "app inside the image does not verify"; }
links=$(find "$mount/calibre-zen.app" -type l | wc -l | tr -d ' ')
hdiutil detach "$mount" >/dev/null
rmdir "$mount"

echo
echo "$DMG"
echo "  $(du -h "$DMG" | cut -f1), $links symlinks intact, signature verifies inside the image"
echo
echo "The signature is ad hoc, so on the receiving Mac:"
echo "  xattr -dr com.apple.quarantine /Applications/calibre-zen.app"
