#!/bin/bash
# Stock calibre-server inside Docker on Linux: image size, start-up, idle
# memory per process, then the same load test as measure-load.sh from outside.
#
#   measure-docker.sh path/to/calibre-<version>-<arch>.txz [clients...]
#
# Memory inside the container is PSS from /proc/<pid>/smaps_rollup: shared
# pages are split between the processes that share them, so it adds up fairly.
# The container's limits are whatever Docker's VM has; they are printed.
. "$(dirname "$0")/lib.sh"
txz="$1"; shift
[ -f "$txz" ] || { echo "usage: $0 calibre-<version>-<arch>.txz [clients...]" >&2; exit 2; }
D="$(dirname "$0")/docker"
W=$(mktemp -d)
mkdir -p "$W/ctx/calibre"
cp "$D/Dockerfile" "$W/ctx/"
tar -xJf "$txz" -C "$W/ctx/calibre"
docker build -q -t zen-measure-server "$W/ctx" >/dev/null || { echo "build failed"; exit 1; }
echo "== Docker: $(docker info --format '{{.OperatingSystem}}, {{.Architecture}}, {{.NCPU}} CPU, {{.MemTotal}} bytes')"
echo "   calibre: $(basename "$txz"), image $(docker image inspect zen-measure-server --format '{{.Size}}' | awk '{printf "%d MB", $1/1e6}')"

lid=$(basename "$LIB")
cp -R "$LIB" "$W/$lid"
chmod -R a+rwX "$W/$lid"
docker rm -f zen-measure >/dev/null 2>&1
t0=$(date +%s)
docker run -d --name zen-measure -p "$PORT:8080" -v "$W/$lid:/library/$lid" zen-measure-server \
    --enable-local-write --trusted-ips 0.0.0.0/0 "/library/$lid" >/dev/null
up=0
for i in $(seq 240); do
    curl -s -o /dev/null "http://127.0.0.1:$PORT/" && { up=1; break; }
    [ "$(docker inspect -f '{{.State.Running}}' zen-measure)" = true ] || break
    sleep 0.5
done
if [ $up = 0 ]; then echo "   the server did not start:"; docker logs zen-measure 2>&1 | tail -15; docker rm -f zen-measure >/dev/null; exit 1; fi
echo "   answering after $(($(date +%s) - t0)) s"
echo "   other containers sharing the VM: $(docker ps --format '{{.Names}}' | grep -vx zen-measure | tr '\n' ' ')"

pss() {
    docker exec zen-measure sh -c 'for p in /proc/[0-9]*; do
        [ -r $p/smaps_rollup ] || continue
        c=$(tr "\0" " " < $p/cmdline | cut -c1-60); [ -z "$c" ] && continue
        r=$(awk "/^Rss:/ {print int(\$2/1024)}" $p/smaps_rollup); s=$(awk "/^Pss:/ {print int(\$2/1024)}" $p/smaps_rollup)
        t=$(ls $p/task | wc -l)
        echo "$s $r $t $c"
    done' | sort -rn | awk -v label="$1" '
        BEGIN { print "-- " label }
        $4 ~ /^\// { printf "     pss %4d MB  rss %4d MB  threads %3d  %s\n", $1, $2, $3, substr($0, index($0,$4)); p += $1; r += $2; t += $3; n++ }
        END { printf "   total pss %4d MB  rss %4d MB  threads %3d  processes %d\n", p, r, t, n }'
}
sleep 5
pss "idle"
curl -s -o /dev/null "http://127.0.0.1:$PORT/interface-data/books-init?library_id=$lid"
for id in $(seq 1 30); do curl -s -o /dev/null "http://127.0.0.1:$PORT/get/thumb/$id/$lid?sz=300x400"; done
pss "after books-init and 30 thumbnails"

MEASURE_BASE="http://127.0.0.1:$PORT" MEASURE_SECONDS="${MEASURE_SECONDS:-15}" "$(dirname "$0")/measure-load.sh" "${@:-1 4 16}" | tail -n +2
docker stats --no-stream --format '   docker stats after load: cpu {{.CPUPerc}}, memory {{.MemUsage}}' zen-measure
pss "after load"
echo "   server log: $(docker logs zen-measure 2>&1 | grep -c Traceback) tracebacks"
docker rm -f zen-measure >/dev/null
rm -rf "$W"
