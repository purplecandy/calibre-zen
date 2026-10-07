# Shared helpers for the measure-*.sh scripts. Source it; do not run it.
# Everything here is macOS-only: ps -M and footprint(1).

REPO="$(cd "$(dirname "$0")/../../../.." && pwd)"
BUNDLE="${CALIBRE_ZEN_BUNDLE:-/Applications/calibre.app}"
MACOS="$BUNDLE/Contents/MacOS"
LIB="${MEASURE_LIBRARY:-$REPO/.calibre-zen/perf-library}"
PORT="${MEASURE_PORT:-18099}"

# pid and every descendant, one per line
tree() {
    echo "$1"
    for c in $(pgrep -P "$1"); do tree "$c"; done
}

# footprint(1) of one pid in MB: the dirty memory Activity Monitor calls "Memory"
fp_mb() {
    footprint "$1" 2>/dev/null | awk '/Footprint:/ {
        for (i = 1; i <= NF; i++) if ($i == "Footprint:") { v = $(i+1); u = $(i+2) }
        if (u == "KB") v /= 1024; else if (u == "GB") v *= 1024
        printf "%d", v; exit }'
}

# One line per process, then a total: RSS, footprint, threads.
# RSS double-counts the shared Qt frameworks; footprint does not.
report() {
    local label="$1" root="$2" rss=0 fp=0 th=0 n=0 p r f t
    echo "-- $label"
    for p in $(tree "$root"); do
        r=$(ps -o rss= -p "$p" 2>/dev/null | tr -d ' ') || continue
        [ -z "$r" ] && continue
        f=$(fp_mb "$p"); f=${f:-0}
        t=$(ps -M -p "$p" 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')
        printf '   %6s  rss %5d MB  footprint %5d MB  threads %3d  %s\n' "$p" $((r / 1024)) "$f" "$t" \
            "$(ps -o command= -p "$p" | sed 's|.*/||' | cut -c1-70)"
        rss=$((rss + r)); fp=$((fp + f)); th=$((th + t)); n=$((n + 1))
    done
    printf '   total   rss %5d MB  footprint %5d MB  threads %3d  processes %d\n' $((rss / 1024)) "$fp" "$th" "$n"
}

cpu_of() { ps -o %cpu= -p "$1" | tr -d ' '; }

# wait until a URL answers, or the pid dies; echoes seconds taken
wait_http() {
    local url="$1" pid="$2" t0 i
    t0=$(date +%s)
    for i in $(seq 240); do
        curl -s -o /dev/null "$url" && { echo $(($(date +%s) - t0)); return 0; }
        kill -0 "$pid" 2>/dev/null || return 1
        sleep 0.5
    done
    return 1
}

# wait until a file contains a line starting with "ready"
wait_ready() {
    local file="$1" pid="$2" i
    for i in $(seq 240); do
        grep -q '^ready' "$file" 2>/dev/null && return 0
        kill -0 "$pid" 2>/dev/null || return 1
        sleep 0.5
    done
    return 1
}

# SIGTERM, then SIGKILL if it is still there 3 s later. calibre's Application
# ignores SIGTERM, and a calibre-server stuck under load does too.
stop() {
    kill "$1" 2>/dev/null
    for _ in 1 2 3 4 5 6; do kill -0 "$1" 2>/dev/null || break; sleep 0.5; done
    if kill -0 "$1" 2>/dev/null; then echo "   (pid $1 ignored SIGTERM; killed)"; kill -9 "$1" 2>/dev/null; fi
    wait "$1" 2>/dev/null
}
