#!/bin/bash
# The full zen GUI, offscreen, on the perf library, 30 s after launch.
#
#   measure-gui.sh develop    as ./calibre-zen runs it: develop mode
#   measure-gui.sh packaged   CALIBRE_ZEN_PACKAGED=1: nothing is recompiled
#   measure-gui.sh lean       packaged, no spare reader, no update check: the
#                             floor for a host that is calibre's own window, unseen
#
# Runs through ./calibre-zen, which records the perf library as library_path in
# the dev config. The next plain ./calibre-zen puts it back.
. "$(dirname "$0")/lib.sh"
mode="${1:-packaged}"
args=()
case "$mode" in
    develop) ;;
    packaged) export CALIBRE_ZEN_PACKAGED=1 ;;
    lean) export CALIBRE_ZEN_PACKAGED=1 CALIBRE_ZEN_READER=0; args=(--no-update-check) ;;
    *) echo "usage: $0 develop|packaged|lean" >&2; exit 2 ;;
esac
if pgrep -f bootstrap.py >/dev/null; then
    echo "a calibre-zen GUI is already running; quit it first" >&2; exit 1
fi
LOG=$(mktemp)
QT_QPA_PLATFORM=offscreen CALIBRE_ZEN_LIBRARY="$LIB" "$REPO/calibre-zen" "${args[@]}" >"$LOG" 2>&1 &
G=$!
echo "== GUI, $mode"
sleep 30
kill -0 $G 2>/dev/null || { echo "GUI exited"; tail "$LOG"; exit 1; }
report "30 s after launch" $G
sleep 10
echo "   main process cpu over the next moment: $(cpu_of $G)%"
pkill -f bootstrap.py; sleep 3; pkill -9 -f bootstrap.py 2>/dev/null; pkill -f calibre_zen.reader.warm 2>/dev/null
wait $G 2>/dev/null
rm -f "$LOG"
