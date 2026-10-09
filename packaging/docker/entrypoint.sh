#!/bin/sh
# calibre-zen in Docker: set up /config and /library, drop from root to
# PUID:PGID, then run calibre-zen's host in the foreground on 0.0.0.0.
#
# Arguments given to `docker run IMAGE ...` are passed to the server as extra
# options, before the library paths: calibre-server's own options all work.
# With --manage-users among them, they go to calibre's user manager instead,
# against /config's user database, and no server starts.
set -eu

ZEN=/opt/calibre-zen
HOST="$ZEN/src/calibre_zen/host/__main__.py"
PREPARE=/usr/local/lib/calibre-zen/prepare.py
USERDB=/config/server-users.sqlite
PORT="${CALIBRE_ZEN_PORT:-8080}"

# What the image itself writes in /config. Only these are re-owned in a
# /config that already has things in it: it may be someone's own folder.
OWN="cache caches plugins conversion fonts global.py.json gui.json gui.py.json
dynamic.pickle.json tweaks.json customize.py.json server-config.txt
server-users.sqlite server-users.sqlite-journal server-users.sqlite-wal
server-users.sqlite-shm"

log() { printf 'calibre-zen: %s\n' "$*" >&2; }
die() { log "$*"; exit 1; }
is_empty() { [ -z "$(ls -A "$1" 2>/dev/null)" ]; }
owner() { stat -c %u:%g "$1"; }

# optparse takes any unique prefix of a long option, so match those too.
# Nothing after a bare -- is an option.
manage=
own_auto_add=
for a in "$@"; do
    case "$a" in
        --) break ;;
        --man*) manage=1 ;;
        --auto-a*|--no*) own_auto_add=1 ;;
    esac
done

# A library kept inside /config, as other calibre images do, would be served
# as an empty new library at /library instead. Stop before touching anything.
if [ -d /config ]; then
    found=$(find /config -maxdepth 3 -name metadata.db -print -quit 2>/dev/null || true)
    if [ -n "$found" ]; then
        die "found a calibre library inside /config, at ${found%/metadata.db}. /config is only for settings. Mount that library folder at /library instead, and give /config an empty folder."
    fi
fi

# ------------------------------------------------------------------ as root
# Own /config, then run the rest of this script as PUID:PGID. /library and
# /auto-add are only chowned while empty: after that they hold someone's books.
if [ "$(id -u)" = 0 ]; then
    PUID="${PUID:-1000}"
    PGID="${PGID:-1000}"
    case "$PUID:$PGID" in
        *[!0-9:]*|:*|*:) die "PUID and PGID must be numbers, got PUID=$PUID PGID=$PGID" ;;
    esac
    [ "$PUID" != 0 ] || die "PUID=0 would run the server as root. Set PUID and PGID to the owner of your books (run: id)."
    mkdir -p /config /library
    if [ "$(owner /config)" != "$PUID:$PGID" ]; then
        log "giving /config to $PUID:$PGID"
        chown "$PUID:$PGID" /config || true
    fi
    for f in $OWN; do
        if [ -e "/config/$f" ] && [ "$(owner "/config/$f")" != "$PUID:$PGID" ]; then
            chown -R "$PUID:$PGID" "/config/$f" || true
        fi
    done
    # A read-only mount cannot be chowned. The checks below say what to do.
    if is_empty /library; then
        chown "$PUID:$PGID" /library 2>/dev/null || true
    fi
    if [ -d /auto-add ] && is_empty /auto-add; then
        chown "$PUID:$PGID" /auto-add 2>/dev/null || true
    fi
    export USER="${USER:-calibre}" LOGNAME="${LOGNAME:-calibre}"
    exec setpriv --reuid="$PUID" --regid="$PGID" --clear-groups -- "$0" "$@"
fi

# ------------------------------------------------------- as the book owner
umask "${UMASK:-022}"
me="$(id -u):$(id -g)"
[ -w /config ] || die "/config is not writable by $me. Set PUID and PGID, or chown the folder."
mkdir -p "${XDG_CACHE_HOME:-/config/cache}"

if [ -n "$manage" ]; then
    exec "$ZEN/zen-bin/zen-calibre-debug" -e "$HOST" -- --userdb "$USERDB" "$@"
fi

# calibre cannot open a library it cannot write to: it writes a test file and
# the database even to list books.
writable() {
    if [ ! -w "$1" ] || { [ -e "$1/metadata.db" ] && [ ! -w "$1/metadata.db" ]; }; then
        die "$1 is not writable by $me, and calibre needs to write to a library even to show it. Mount it read-write, and set PUID and PGID to the owner of the books (run: id)."
    fi
}

# Which libraries: /library itself, or each folder in it that holds one, or
# a new empty one when /library is empty. `set --` appends each path to the
# arguments, so names with spaces survive in POSIX sh.
create=
nlibs=0
if [ -f /library/metadata.db ]; then
    writable /library
    set -- "$@" /library
    nlibs=1
else
    for d in /library/*/; do
        if [ -f "${d}metadata.db" ]; then
            writable "${d%/}"
            set -- "$@" "${d%/}"
            nlibs=$((nlibs + 1))
        fi
    done
fi
if [ "$nlibs" = 0 ]; then
    if is_empty /library; then
        writable /library
        create=/library
        set -- "$@" /library
    else
        die "/library has files but no calibre library (no metadata.db). Mount a calibre library folder there, or an empty folder for a new library. To import loose books, mount them at /auto-add."
    fi
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

# The host refuses to start with an --auto-add folder it cannot use, so only
# name /auto-add when it can. A folder Docker made for a missing bind source
# is root's, and was given to PUID above while empty.
if [ -z "$own_auto_add" ]; then
    if [ ! -d /auto-add ]; then
        set -- --no-auto-add "$@"
    elif [ -r /auto-add ] && [ -w /auto-add ] && [ -x /auto-add ]; then
        set -- --auto-add /auto-add "$@"
    else
        log "not adding books from /auto-add: $me cannot read and write it. Mount it read-write and give it to $me to turn it on."
        set -- --no-auto-add "$@"
    fi
fi
log "starting the host on port $PORT"
set -- "$ZEN/zen-bin/zen-calibre-debug" -e "$HOST" -- "$@"
exec "$@"
