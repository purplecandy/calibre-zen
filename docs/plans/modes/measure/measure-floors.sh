#!/bin/bash
# The smallest pieces a background host or a Mini window could be built from,
# each held idle and measured, plus how long one calibredb command takes.
#
#   measure-floors.sh            all of them
#   measure-floors.sh go db      only the named cases
#
# Cases: python db qt-tray qt-window-bare qt-window zen-window-bare zen-window go calibredb
. "$(dirname "$0")/lib.sh"
W=$(mktemp -d)
export CALIBRE_CONFIG_DIRECTORY="$W/config"
cases="${*:-python db qt-tray qt-window-bare qt-window zen-window-bare zen-window go calibredb}"

# run "$@" in the background, wait for it to print "ready", measure, stop it
hold() {
    local label="$1"; shift
    "$@" >"$W/out" 2>&1 &
    local p=$!
    if ! wait_ready "$W/out" $p; then echo "-- $label: did not start"; tail -5 "$W/out"; stop $p; return; fi
    sleep 3
    report "$label ($(grep '^ready' "$W/out" | head -1))" $p
    stop $p
}


cat >"$W/python.py" <<'PY'
import time
print('ready', flush=True)
time.sleep(600)
PY

cat >"$W/db.py" <<'PY'
import sys, time
from calibre.db.legacy import LibraryDatabase
db = LibraryDatabase(sys.argv[-1])
print('ready', len(db.new_api.all_book_ids()), 'books', flush=True)
time.sleep(600)
PY

# A tray icon with a small menu, on a plain QApplication: no calibre look.
cat >"$W/tray.py" <<'PY'
from qt.core import QApplication, QIcon, QMenu, QPixmap, QSystemTrayIcon, QTimer
app = QApplication([])
pm = QPixmap(22, 22)
pm.fill()
tray = QSystemTrayIcon(QIcon(pm))
menu = QMenu()
for t in ('Server: running', 'Open calibre', 'Open Mini', 'Settings', 'Quit'):
    menu.addAction(t)
tray.setContextMenu(menu)
tray.show()
QTimer.singleShot(0, lambda: print('ready', flush=True))
app.exec()
PY

# A Mini-shaped window: every cover in the library as a 100x150 tile in a list.
# Covers come off the disk, the way an HTTP client would hold them once fetched.
# Every tile is decoded up front (100x150x4 bytes each), so the difference from
# the bare case is the cost of holding all covers, which a real view would not.
# sys.argv: library, then "zen" for calibre's Application (the zen look) and/or
# "bare" for titles only, no covers.
cat >"$W/window.py" <<'PY'
import os, sys
zen, bare = 'zen' in sys.argv, 'bare' in sys.argv
lib = next(a for a in sys.argv[1:] if os.path.isdir(a))
if zen:
    from calibre.gui2 import Application
    app = Application([], force_calibre_style=True)
else:
    from qt.core import QApplication
    app = QApplication([])
from qt.core import QIcon, QListView, QPixmap, QSize, QStandardItem, QStandardItemModel, Qt, QTimer
model = QStandardItemModel()
n = 0
for root, dirs, files in os.walk(lib):
    if 'cover.jpg' in files and bare:
        model.appendRow(QStandardItem(os.path.basename(root)))
        n += 1
    elif 'cover.jpg' in files:
        pm = QPixmap(os.path.join(root, 'cover.jpg')).scaled(100, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        model.appendRow(QStandardItem(QIcon(pm), os.path.basename(root)))
        n += 1
view = QListView()
view.setViewMode(QListView.ViewMode.IconMode)
view.setIconSize(QSize(100, 150))
view.setModel(model)
view.resize(900, 700)
view.show()
QTimer.singleShot(500, lambda: print('ready', n, 'books', flush=True))
app.exec()
PY

cat >"$W/main.go" <<'GO'
package main

import (
	"fmt"
	"net/http"
	"os"
)

func main() {
	http.HandleFunc("/status", func(w http.ResponseWriter, r *http.Request) { fmt.Fprintln(w, `{"ok":true}`) })
	fmt.Println("ready")
	os.Stdout.Sync()
	http.ListenAndServe("127.0.0.1:"+os.Args[1], nil)
}
GO

for c in $cases; do
    case "$c" in
    python) hold "python: calibre's interpreter, nothing imported" "$MACOS/calibre-debug" -e "$W/python.py" ;;
    db) hold "db: one library open, no Qt, no server" "$MACOS/calibre-debug" -e "$W/db.py" -- "$LIB" ;;
    qt-tray) QT_QPA_PLATFORM=offscreen hold "qt-tray: QApplication + tray icon + menu" "$MACOS/calibre-debug" -e "$W/tray.py" ;;
    qt-window-bare) QT_QPA_PLATFORM=offscreen hold "qt-window-bare: plain Qt, title list" "$MACOS/calibre-debug" -e "$W/window.py" -- "$LIB" bare ;;
    zen-window-bare)
        CALIBRE_DEVELOP_FROM="$REPO/src" CALIBRE_ZEN_PACKAGED=1 QT_QPA_PLATFORM=offscreen \
            hold "zen-window-bare: calibre Application with the zen look, title list" \
            "$MACOS/calibre-debug" -e "$W/window.py" -- "$LIB" zen bare ;;
    qt-window) QT_QPA_PLATFORM=offscreen hold "qt-window: plain Qt, cover list" "$MACOS/calibre-debug" -e "$W/window.py" -- "$LIB" ;;
    zen-window)
        CALIBRE_DEVELOP_FROM="$REPO/src" CALIBRE_ZEN_PACKAGED=1 QT_QPA_PLATFORM=offscreen \
            hold "zen-window: calibre Application with the zen look, cover list" \
            "$MACOS/calibre-debug" -e "$W/window.py" -- "$LIB" zen ;;
    go)
        if ! command -v go >/dev/null; then echo "-- go: not installed"; continue; fi
        (cd "$W" && GOFLAGS=-mod=mod go mod init m >/dev/null 2>&1; go build -o "$W/gohost" main.go) || { echo "-- go: build failed"; continue; }
        hold "go: net/http with one /status route" "$W/gohost" "$PORT" ;;
    calibredb)
        echo "-- calibredb: one 'list --limit 1', three times each"
        for i in 1 2 3; do
            /usr/bin/time -l "$MACOS/calibredb" list --limit 1 --with-library "$LIB" >/dev/null 2>"$W/t"
            awk '/real/ {r=$1} /maximum resident/ {m=int($1/1048576)} END {printf "   local, opens the library itself:  %ss, peak rss %d MB\n", r, m}' "$W/t"
        done
        "$MACOS/calibre-server" --port "$PORT" --enable-local-write "$LIB" >"$W/srv" 2>&1 &
        S=$!
        wait_http "http://127.0.0.1:$PORT/" $S >/dev/null || { echo "   server did not start"; continue; }
        for i in 1 2 3; do
            /usr/bin/time -l "$MACOS/calibredb" list --limit 1 --with-library "http://127.0.0.1:$PORT/#$(basename "$LIB")" >/dev/null 2>"$W/t"
            awk '/real/ {r=$1} /maximum resident/ {m=int($1/1048576)} END {printf "   remote, through a running server: %ss, peak rss %d MB\n", r, m}' "$W/t"
        done
        t=$(curl -s -o /dev/null -w '%{time_total}' "http://127.0.0.1:$PORT/ajax/search/$(basename "$LIB")?query=&num=1")
        echo "   the same question as one HTTP request: ${t}s"
        stop $S ;;
    *) echo "-- unknown case $c" ;;
    esac
done
rm -rf "$W"
