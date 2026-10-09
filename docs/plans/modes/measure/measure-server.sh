#!/bin/bash
# calibre-server on the perf library: idle, then after the web app's first page
# of books and 30 cover thumbnails.
#
#   docs/plans/modes/measure/measure-server.sh            stock, as packaged
#   MEASURE_DEVELOP=1 docs/plans/modes/measure/...        from ./src, develop mode
. "$(dirname "$0")/lib.sh"
CFG=$(mktemp -d)
if [ "${MEASURE_DEVELOP:-0}" = 1 ]; then
    export CALIBRE_DEVELOP_FROM="$REPO/src"; label="calibre-server, develop mode"
else
    label="calibre-server, stock"
fi
CALIBRE_CONFIG_DIRECTORY=$CFG "$MACOS/calibre-server" --port "$PORT" "$LIB" >"$CFG/log" 2>&1 &
S=$!
secs=$(wait_http "http://127.0.0.1:$PORT/" $S) || { echo "server died"; tail "$CFG/log"; exit 1; }
echo "== $label: answering after ${secs}s"
sleep 5
report "idle" $S
lid=$(basename "$LIB")
curl -s -o /dev/null -w "   books-init %{http_code} in %{time_total}s\n" \
    "http://127.0.0.1:$PORT/interface-data/books-init?library_id=$lid"
for id in $(seq 1 30); do curl -s -o /dev/null "http://127.0.0.1:$PORT/get/thumb/$id/$lid?sz=300x400"; done
sleep 3
report "after browsing" $S
sleep 15
echo "   idle cpu: $(cpu_of $S)%"
stop $S
rm -rf "$CFG"
