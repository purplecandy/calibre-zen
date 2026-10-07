#!/bin/sh
# Docker's HEALTHCHECK: is the server answering on its port?
#
# With calibre-zen's host in the image, /zen/status must answer 200; it does
# without a login from inside the container. Until then calibre-server has no
# status page, so any answer from / counts, including 401 when login is on.
base="http://127.0.0.1:${CALIBRE_ZEN_PORT:-8080}${CALIBRE_ZEN_URL_PREFIX:-}"
base="${base%/}"
if [ -f /opt/calibre-zen/src/calibre_zen/host/__main__.py ]; then
    exec curl -fsS -o /dev/null --max-time 5 "$base/zen/status"
fi
code=$(curl -s -o /dev/null --max-time 5 -w '%{http_code}' "$base/") || exit 1
case "$code" in
    200|401) exit 0 ;;
    *) echo "calibre-server answered $code" >&2; exit 1 ;;
esac
