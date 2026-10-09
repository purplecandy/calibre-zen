#!/bin/bash
# The same tiny program in each language installed here: an HTTP server on
# localhost with one /status route, using only the standard library. Measures
# idle memory, time to first answer and the size of what would ship.
#
#   measure-languages.sh              every language found
#   measure-languages.sh go rust      only these
#
# Languages: go rust swift java node bun python
. "$(dirname "$0")/lib.sh"
W=$(mktemp -d)
langs="${*:-go rust swift java node bun python}"


# $1 label, $2 what ships (path or note), rest: the command
hold() {
    local label="$1" ships="$2"; shift 2
    local t0 t1 p
    t0=$(python3 -c 'import time; print(time.time())')
    "$@" >"$W/out" 2>&1 &
    p=$!
    for _ in $(seq 400); do
        curl -s -o /dev/null "http://127.0.0.1:$PORT/status" && break
        kill -0 $p 2>/dev/null || { echo "-- $label: exited"; tail -3 "$W/out"; return; }
        sleep 0.05
    done
    t1=$(python3 -c 'import time; print(time.time())')
    for _ in $(seq 100); do curl -s -o /dev/null "http://127.0.0.1:$PORT/status"; done
    sleep 2
    printf -- '-- %s: first answer after %.2fs, ships %s\n' "$label" "$(echo "$t1 - $t0" | bc)" "$ships"
    report "after 100 requests, idle" $p | tail -1
    stop $p
}

size() { du -sh "$1" | cut -f1; }

for l in $langs; do
    case $l in
    go)
        cat >"$W/main.go" <<'X'
package main

import (
	"fmt"
	"net/http"
	"os"
)

func main() {
	http.HandleFunc("/status", func(w http.ResponseWriter, r *http.Request) { fmt.Fprintln(w, `{"ok":true}`) })
	http.ListenAndServe("127.0.0.1:"+os.Args[1], nil)
}
X
        (cd "$W" && go mod init m >/dev/null 2>&1; go build -ldflags=-s -o gohost main.go) &&
            hold "Go $(go env GOVERSION)" "a $(size "$W/gohost") binary" "$W/gohost" "$PORT" ;;
    rust)
        cat >"$W/main.rs" <<'X'
use std::io::{Read, Write};
use std::net::TcpListener;
fn main() {
    let port = std::env::args().nth(1).unwrap();
    let l = TcpListener::bind(format!("127.0.0.1:{port}")).unwrap();
    for s in l.incoming() {
        let mut s = s.unwrap();
        let mut buf = [0u8; 4096];
        let _ = s.read(&mut buf);
        let body = "{\"ok\":true}\n";
        let _ = write!(s, "HTTP/1.1 200 OK\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}", body.len(), body);
    }
}
X
        rustc -O -C strip=symbols -o "$W/rshost" "$W/main.rs" 2>/dev/null &&
            hold "Rust $(rustc --version | cut -d' ' -f2), std only, single-threaded" "a $(size "$W/rshost") binary" "$W/rshost" "$PORT" ;;
    swift)
        cat >"$W/main.swift" <<'X'
import Darwin
let port = UInt16(CommandLine.arguments[1])!
let fd = socket(AF_INET, SOCK_STREAM, 0)
var yes: Int32 = 1
setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, socklen_t(MemoryLayout<Int32>.size))
var addr = sockaddr_in()
addr.sin_family = sa_family_t(AF_INET)
addr.sin_port = port.bigEndian
addr.sin_addr.s_addr = inet_addr("127.0.0.1")
_ = withUnsafePointer(to: &addr) { $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) } }
listen(fd, 16)
let body = "{\"ok\":true}\n"
let resp = "HTTP/1.1 200 OK\r\nContent-Length: \(body.utf8.count)\r\nConnection: close\r\n\r\n\(body)"
var buf = [UInt8](repeating: 0, count: 4096)
while true {
    let c = accept(fd, nil, nil)
    _ = read(c, &buf, 4096)
    _ = resp.withCString { write(c, $0, strlen($0)) }
    close(c)
}
X
        swiftc -O -o "$W/swhost" "$W/main.swift" 2>/dev/null &&
            hold "Swift $(swiftc --version 2>&1 | sed -n 's/.*Swift version \([0-9.]*\).*/\1/p'), Darwin sockets" "a $(size "$W/swhost") binary (macOS only)" "$W/swhost" "$PORT" ;;
    java)
        cat >"$W/Main.java" <<'X'
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
public class Main {
    public static void main(String[] a) throws Exception {
        HttpServer s = HttpServer.create(new InetSocketAddress("127.0.0.1", Integer.parseInt(a[0])), 0);
        s.createContext("/status", x -> { byte[] b = "{\"ok\":true}\n".getBytes(); x.sendResponseHeaders(200, b.length); x.getResponseBody().write(b); x.close(); });
        s.start();
    }
}
X
        (cd "$W" && javac Main.java 2>/dev/null) &&
            hold "Java $(java -version 2>&1 | head -1 | cut -d'"' -f2), default JVM" "the class plus a JVM (~$(size "$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")"))" java -cp "$W" Main "$PORT" ;;
    node)
        cat >"$W/main.js" <<'X'
require('http').createServer((q, r) => { r.end('{"ok":true}\n') }).listen(+process.argv[2], '127.0.0.1')
X
        hold "Node $(node --version)" "the script plus Node (~$(size "$(command -v node)"))" node "$W/main.js" "$PORT" ;;
    bun)
        cat >"$W/bun.js" <<'X'
Bun.serve({ hostname: '127.0.0.1', port: +process.argv[2], fetch: () => new Response('{"ok":true}\n') })
X
        (cd "$W" && bun build --compile bun.js --outfile bunhost >/dev/null 2>&1) &&
            hold "Bun $(bun --version), compiled" "a $(size "$W/bunhost") binary" "$W/bunhost" "$PORT" ;;
    python)
        cat >"$W/main.py" <<'X'
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"ok":true}\n')
    def log_message(self, *a): pass
ThreadingHTTPServer(('127.0.0.1', int(sys.argv[1])), H).serve_forever()
X
        hold "Python $(python3 -c 'import sys; print(sys.version.split()[0])'), standard library" "the script plus Python" python3 "$W/main.py" "$PORT" ;;
    *) echo "-- unknown language $l" ;;
    esac
done
rm -rf "$W"
