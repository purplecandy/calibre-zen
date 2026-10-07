#!/bin/sh
# calibre-zen in Docker: set up /config and /library, drop from root to
# PUID:PGID, then run calibre-zen's host in the foreground on 0.0.0.0.
#
# Arguments given to `docker run IMAGE ...` are passed to the server as extra
# options, before the library paths: calibre-server's own options all work.
set -eu

ZEN=/opt/calibre-zen
HOST="$ZEN/src/calibre_zen/host/__main__.py"
PREPARE=/usr/local/lib/calibre-zen/prepare.py
USERDB=/config/server-users.sqlite
PORT="${CALIBRE_ZEN_PORT:-8080}"

log() { printf 'calibre-zen: %s\n' "$*" >&2; }
die() { log "$*"; exit 1; }
is_empty() { [ -z "$(ls -A "$1" 2>/dev/null)" ]; }

# ------------------------------------------------------------------ as root
# Own /config, then run the rest of this script as PUID:PGID. /library is
# never chowned once it has anything in it: those are the person's books.
if [ "$(id -u)" = 0 ]; then
    PUID="${PUID:-1000}"
    PGID="${PGID:-1000}"
    case "$PUID:$PGID" in
        *[!0-9:]*|:*|*:) die "PUID and PGID must be numbers, got PUID=$PUID PGID=$PGID" ;;
    esac
    [ "$PUID" != 0 ] || die "PUID=0 would run the server as root. Set PUID and PGID to the owner of your books (run: id)."
    mkdir -p /config /library
    if [ "$(stat -c %u:%g /config)" != "$PUID:$PGID" ]; then
        log "giving /config to $PUID:$PGID"
        chown -R "$PUID:$PGID" /config
    fi
    if is_empty /library; then
        chown "$PUID:$PGID" /library
    fi
    export USER="${USER:-calibre}" LOGNAME="${LOGNAME:-calibre}"
    exec setpriv --reuid="$PUID" --regid="$PGID" --clear-groups -- "$0" "$@"
fi

# ------------------------------------------------------- as the book owner
umask "${UMASK:-022}"
me="$(id -u):$(id -g)"
[ -w /config ] || die "/config is not writable by $me. Set PUID and PGID, or chown the folder."
mkdir -p "${XDG_CACHE_HOME:-/config/cache}"

# Which libraries: /library itself, or each folder in it that holds one, or
# a new empty one when /library is empty. `set --` appends each path to the
# arguments, so names with spaces survive in POSIX sh.
create=
nlibs=0
if [ -f /library/metadata.db ]; then
    set -- "$@" /library
    nlibs=1
else
    for d in /library/*/; do
        if [ -f "${d}metadata.db" ]; then
            set -- "$@" "${d%/}"
            nlibs=$((nlibs + 1))
        fi
    done
fi
if [ "$nlibs" = 0 ]; then
    if is_empty /library; then
        create=/library
        set -- "$@" /library
    else
        die "/library has files but no calibre library (no metadata.db). Mount a calibre library folder there, or an empty folder for a new library. To import loose books, mount them at /auto-add."
    fi
fi
if [ ! -w /library ] && [ -z "$create" ]; then
    log "/library is not writable by $me: books can be read but not changed"
fi

# Create the library if needed, add or update the login user, and learn
# whether any user exists. The last line of output is "auth=0" or "auth=1".
if [ -n "$create" ]; then
    out=$("$ZEN/zen-bin/zen-calibre-debug" -e "$PREPARE" -- "$USERDB" --create-library "$create") || die "start-up failed (above)"
else
    out=$("$ZEN/zen-bin/zen-calibre-debug" -e "$PREPARE" -- "$USERDB") || die "start-up failed (above)"
fi
case "$(printf '%s\n' "$out" | tail -n 1)" in
    auth=1) auth=1 ;;
    auth=0) auth=0 ;;
    *) die "start-up gave an unexpected answer: $out" ;;
esac

# The options this image always sets. They go in front, so anything given to
# `docker run` after the image name comes later and wins.
if [ -n "${CALIBRE_ZEN_TRUSTED_IPS:-}" ]; then
    set -- --trusted-ips "$CALIBRE_ZEN_TRUSTED_IPS" "$@"
fi
if [ -n "${CALIBRE_ZEN_URL_PREFIX:-}" ]; then
    set -- --url-prefix "$CALIBRE_ZEN_URL_PREFIX" "$@"
fi
if [ "$auth" = 1 ]; then
    set -- --enable-auth "$@"
    log "login is on; signed-in users can add and change books"
elif [ -n "${CALIBRE_ZEN_TRUSTED_IPS:-}" ]; then
    log "login is off; visitors from $CALIBRE_ZEN_TRUSTED_IPS can add and change books"
else
    log "login is off, so visitors can read but not change books. Set CALIBRE_ZEN_USERNAME and CALIBRE_ZEN_PASSWORD to allow changes."
fi
set -- --listen-on 0.0.0.0 --port "$PORT" --disable-use-bonjour --userdb "$USERDB" "$@"

if [ -d /auto-add ]; then
    set -- --auto-add /auto-add "$@"
else
    set -- --no-auto-add "$@"
fi
log "starting the host on port $PORT"
set -- "$ZEN/zen-bin/zen-calibre-debug" -e "$HOST" -- "$@"
exec "$@"
