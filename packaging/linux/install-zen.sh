#!/bin/sh
# Download and install the latest Linux release, or install a local tarball.
set -eu

die() {
    printf 'install-zen.sh: %s\n' "$*" >&2
    exit 1
}

check_install() {
    root=$1
    for file in calibre bin/calibre zen-bin/calibre-zen calibre-zen; do
        [ -x "$root/$file" ] || die "installation is incomplete: missing $root/$file. Re-download and re-extract the tarball."
    done
}

case "${1:-}" in
    --check)
        [ "$#" -eq 1 ] || die 'usage: install-zen.sh --check | --latest | <tarball.txz>'
        root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
        check_install "$root"
        printf 'Installation is complete: %s\n' "$root"
        exit 0
        ;;
    --latest)
        [ "$#" -eq 1 ] || die 'usage: install-zen.sh --check | --latest | <tarball.txz>'
        [ ! -e calibre-zen ] && [ ! -L calibre-zen ] || die 'calibre-zen already exists here. Move it aside before installing a new copy.'
        command -v curl >/dev/null 2>&1 || die 'curl is needed to download the release'
        case "$(uname -m)" in
            x86_64) arch=x86_64 ;;
            aarch64|arm64) arch=arm64 ;;
            *) die 'this release supports x86_64 and arm64 Linux' ;;
        esac
        release=$(curl -fsSL -o /dev/null -w '%{url_effective}' \
            https://github.com/purplecandy/calibre-zen/releases/latest) || die 'could not find the latest release'
        case "$release" in
            https://github.com/purplecandy/calibre-zen/releases/tag/v*)
                version=${release##*/v} ;;
            *) die "unexpected release URL: $release" ;;
        esac
        archive="calibre-zen-$version-linux-$arch.txz"
        base="https://github.com/purplecandy/calibre-zen/releases/download/v$version"
        for file in "$archive" "$archive.sha256"; do
            printf 'Downloading %s\n' "$file"
            if ! curl -fL --retry 3 -o "$file.part" "$base/$file"; then
                rm -f "$file.part"
                die "could not download $file"
            fi
            mv "$file.part" "$file"
        done
        ;;
    '') die 'usage: install-zen.sh --check | --latest | <tarball.txz>' ;;
    *)
        [ "$#" -eq 1 ] || die 'usage: install-zen.sh --check | --latest | <tarball.txz>'
        archive=$1
        ;;
esac

for tool in tar xz sha256sum; do
    command -v "$tool" >/dev/null 2>&1 || die "$tool is needed to install the release"
done
[ -f "$archive" ] || die "missing $archive"
[ -f "$archive.sha256" ] || die "missing $archive.sha256"
[ ! -e calibre-zen ] && [ ! -L calibre-zen ] || die 'calibre-zen already exists here. Move it aside before installing a new copy.'

archive_dir=$(dirname -- "$archive")
archive_name=$(basename -- "$archive")
printf 'Checking %s\n' "$archive_name"
(CDPATH='' cd -- "$archive_dir" && sha256sum -c "$archive_name.sha256") || die 'checksum failed; download the files again'

stage=".calibre-zen-install-$$"
mkdir "$stage" || die "could not create $stage"
trap 'rm -rf "$stage"' 0
trap 'exit 1' 1 2 3 15
printf 'Extracting %s\n' "$archive_name"
tar -xJf "$archive" -C "$stage" || die 'extraction stopped early; check free disk space and try again'
check_install "$stage/calibre-zen"
mv "$stage/calibre-zen" ./calibre-zen
rmdir "$stage"
trap - 0 1 2 3 15
printf 'Ready. Run ./calibre-zen/calibre-zen --version to check it, then ./calibre-zen/calibre-zen to open it.\n'
