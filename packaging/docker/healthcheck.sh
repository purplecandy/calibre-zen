#!/bin/sh
# Docker's HEALTHCHECK: does the host answer /zen/status? It does without a
# login from inside the container.
base="http://127.0.0.1:${CALIBRE_ZEN_PORT:-8080}${CALIBRE_ZEN_URL_PREFIX:-}"
base="${base%/}"
exec curl -fsS -o /dev/null --max-time 5 "$base/zen/status"
