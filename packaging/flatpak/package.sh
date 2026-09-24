#!/bin/bash
# Wrap the already verified Linux release archive as a Flatpak bundle.
# Run after packaging/linux/package.sh on an x86_64 or arm64 Linux host.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
APP_ID=io.github.purplecandy.calibre-zen
ZEN_VERSION=$(sed -n "s/^zen_version = '\([^']*\)'/\1/p" "$REPO/src/calibre/constants.py")
[ -n "$ZEN_VERSION" ] || { echo 'no zen_version in constants.py' >&2; exit 1; }

ARCH="${1:-$(uname -m)}"
case "$ARCH" in
    x86_64|amd64) ARCH=x86_64 ;;
    aarch64|arm64) ARCH=arm64 ;;
    *) echo "unsupported architecture: $ARCH" >&2; exit 1 ;;
esac
[ "$(uname -s)" = Linux ] || { echo 'Flatpak packaging runs on Linux' >&2; exit 1; }
for tool in flatpak flatpak-builder sha256sum bzip2 xz; do
    command -v "$tool" >/dev/null || { echo "need $tool" >&2; exit 1; }
done

DIST="${CALIBRE_ZEN_DIST_DIR:-$REPO/dist}"
BUILD="${CALIBRE_ZEN_FLATPAK_BUILD_DIR:-$REPO/build/flatpak-$ARCH}"
NAME="calibre-zen-$ZEN_VERSION-linux-$ARCH"
TARBALL="$DIST/$NAME.txz"
[ -f "$TARBALL" ] || { echo "missing $TARBALL; run packaging/linux/package.sh $ARCH first" >&2; exit 1; }
(cd "$DIST" && sha256sum -c "$NAME.txz.sha256")

rm -rf "$BUILD"
mkdir -p "$BUILD/context" "$DIST"
cp "$TARBALL" "$BUILD/context/calibre-zen.txz"
cp "$REPO/packaging/flatpak/io.github.purplecandy.calibre-zen.yml" "$BUILD/context/"
cp "$REPO/packaging/flatpak/flatpak-launch" "$BUILD/context/"
cp "$REPO/packaging/flatpak/io.github.purplecandy.calibre-zen.metainfo.xml" "$BUILD/context/"
cp "$REPO/LICENSE" "$BUILD/context/"

flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
(cd "$BUILD" && flatpak-builder --user --force-clean --disable-rofiles-fuse --install-deps-from=flathub \
    --repo="$BUILD/repo" "$BUILD/app" "$BUILD/context/$APP_ID.yml")

FILES="$BUILD/app/files"
for path in \
    "share/applications/$APP_ID.desktop" \
    "share/applications/$APP_ID.ebook-viewer.desktop" \
    "share/applications/$APP_ID.ebook-edit.desktop" \
    "share/icons/hicolor/256x256/apps/$APP_ID.png" \
    "share/icons/hicolor/256x256/apps/$APP_ID.ebook-viewer.png" \
    "share/icons/hicolor/256x256/apps/$APP_ID.ebook-edit.png" \
    "share/metainfo/$APP_ID.metainfo.xml"; do
    [ -s "$FILES/$path" ] || { echo "Flatpak is missing $path" >&2; exit 1; }
done

flatpak-builder --run "$BUILD/app" "$BUILD/context/$APP_ID.yml" \
    /bin/sh -c 'CALIBRE_CONFIG_DIRECTORY=/tmp/calibre-zen-smoke calibre-zen --version'

OUT="$DIST/calibre-zen-$ZEN_VERSION-linux-$ARCH.flatpak"
flatpak build-bundle "$BUILD/repo" "$OUT" "$APP_ID" \
    --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo
(cd "$DIST" && sha256sum "$(basename "$OUT")" > "$(basename "$OUT").sha256")
echo "done: $OUT"
