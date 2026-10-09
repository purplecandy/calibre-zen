#!/bin/sh
# Start an image the way the README does, with a login and an auto-add
# folder, and check that it answers, refuses an anonymous request, takes a
# book from the folder and stops cleanly. The CI workflows run this on every
# image before it is published.
#
#   packaging/docker/check-image.sh IMAGE [PORT]
set -eu
image="$1"
port="${2:-18080}"
name="zen-check-$$"
work=$(mktemp -d)
mkdir -p "$work/library" "$work/config" "$work/auto-add"
book="$work/auto-add/Check Book - CI.txt"

fail() {
    echo "check-image: $*" >&2
    docker logs "$name" >&2 || true
    docker rm -f "$name" >/dev/null 2>&1 || true
    exit 1
}

docker run -d --name "$name" -p "$port:8080" \
    -e PUID="$(id -u)" -e PGID="$(id -g)" \
    -e CALIBRE_ZEN_USERNAME=reader -e CALIBRE_ZEN_PASSWORD=ci-check-pass \
    -v "$work/library:/library" -v "$work/config:/config" -v "$work/auto-add:/auto-add" \
    "$image" >/dev/null

up=0
for _ in $(seq 120); do
    if curl -fs -o /dev/null "http://127.0.0.1:$port/zen/status"; then up=1; break; fi
    sleep 1
done
[ "$up" = 1 ] || fail "it did not answer within two minutes"
curl -fsS "http://127.0.0.1:$port/zen/status"; echo

code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$port/ajax/library-info")
[ "$code" = 401 ] || fail "an anonymous request got $code, not 401"

printf 'A line of text.\n' > "$book"
for _ in $(seq 60); do
    [ -e "$book" ] || break
    sleep 1
done
[ ! -e "$book" ] || fail "auto-add did not take the file"

docker stop -t 30 "$name" >/dev/null
rc=$(docker inspect -f '{{.State.ExitCode}}' "$name")
if docker logs "$name" 2>&1 | grep -q Traceback; then fail "the log has a traceback"; fi
[ "$rc" = 0 ] || fail "it exited with $rc"
docker rm "$name" >/dev/null
echo "check-image: $image works"
