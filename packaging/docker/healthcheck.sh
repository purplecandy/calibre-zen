#!/bin/sh
# Docker's HEALTHCHECK: does the host answer /zen/status? It does without a
# login from inside the container. Plain http first, then https without
# checking the certificate, for a host given --ssl-certfile here or in
# server-config.txt.
url="127.0.0.1:${CALIBRE_ZEN_PORT:-8080}${CALIBRE_ZEN_URL_PREFIX:-}"
url="${url%/}/zen/status"
curl -fsS -o /dev/null --max-time 4 "http://$url" 2>/dev/null ||
    exec curl -kfsS -o /dev/null --max-time 4 "https://$url"
