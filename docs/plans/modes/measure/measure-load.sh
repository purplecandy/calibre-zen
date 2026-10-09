#!/bin/bash
# calibre-server under many readers at once, with a few writes, on a throwaway
# copy of the perf library. For each number of clients: throughput, latency,
# errors, and the server's CPU and memory while it runs.
#
#   measure-load.sh              1, 4, 16 and 32 clients, 15 s each
#   measure-load.sh 8 64         those client counts instead
#
# MEASURE_BASE=http://host:port skips starting a server and loads that one,
# for a server in Docker. MEASURE_SECONDS and MEASURE_WRITES (a ratio, 0.05)
# change the run.
. "$(dirname "$0")/lib.sh"
levels="${*:-1 4 16 32}"
secs="${MEASURE_SECONDS:-15}"
writes="${MEASURE_WRITES:-0.05}"
lid=$(basename "$LIB")
books=$(sqlite3 "$LIB/metadata.db" 'select max(id) from books')
W=$(mktemp -d)

if [ -z "$MEASURE_BASE" ]; then
    cp -R "$LIB" "$W/$lid"
    CALIBRE_CONFIG_DIRECTORY="$W/config" "$MACOS/calibre-server" --port "$PORT" --enable-local-write \
        --disable-use-bonjour "$W/$lid" >"$W/log" 2>&1 &
    S=$!
    wait_http "http://127.0.0.1:$PORT/" $S >/dev/null || { echo "server did not start"; tail "$W/log"; exit 1; }
    base="http://127.0.0.1:$PORT"
    echo "== calibre-server on this Mac, $books books, writes ${writes}"
else
    base="$MEASURE_BASE"
    echo "== $base, $books books, writes ${writes}"
fi

for n in $levels; do
    rm -f "$W/stop"
    if [ -n "$S" ]; then
        ( peak=0; cpu=0; k=0
          while kill -0 $S 2>/dev/null && [ ! -f "$W/stop" ]; do
              c=$(ps -o %cpu= -p $S | tr -d ' '); f=$(fp_mb $S)
              cpu=$(echo "$cpu + ${c:-0}" | bc); k=$((k + 1)); [ "${f:-0}" -gt $peak ] && peak=$f
              sleep 1
          done
          echo "     server: average cpu $(echo "scale=0; $cpu / ($k + (k == 0))" | bc)%, peak footprint ${peak} MB" >"$W/sample" ) &
        sampler=$!
    fi
    python3 "$(dirname "$0")/load.py" --base "$base" --library "$lid" --books "$books" \
        --clients "$n" --seconds "$secs" --write-ratio "$writes"
    if [ -n "$S" ]; then touch "$W/stop"; wait $sampler; cat "$W/sample"; fi
done

if [ -n "$S" ]; then
    errs=$(grep -c 'Traceback' "$W/log")
    echo "   server log: $errs tracebacks"
    grep -h '^[a-zA-Z.]*Error' "$W/log" | sort | uniq -c | sort -rn | head -5 | sed 's/^/     /'
    stop $S
fi
rm -rf "$W"
