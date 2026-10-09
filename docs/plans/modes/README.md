# Headless and Mini modes

Research for two new ways to run calibre-zen. Started 2026-10-08. Nothing is built yet.

- **Headless** runs in the background, from the menubar on macOS and the tray elsewhere. It shows status and simple settings, and starts only what it needs. Later it ships as a Docker image people run on their own server.
- **Mini** is like a mini music player, or Readest. It browses, reads and adds books. It is not a library manager. It should be light, calm and focused.

## Decisions so far

- **A server process owns the library** while zen runs in the background. The full GUI is not kept running unseen.
- **Mini is a client of that process** over HTTP, so both run at once.
- **Headless does what calibre does without its UI.** Above all that is the content server. It also covers auto-add, device sync, news, plugins and other syncing.
- **Headless comes first.**
- **Leaning towards path A**, a lean host. See below.
- **The two server bugs are worked around in zen's own process for now**, and sent upstream as a pull request later. The notes for that pull request are in [upstream-bugs.md](upstream-bugs.md).
- **Go is dropped.** The host and the tray are both Python. The measurements show calibre's Python is fast enough here, and its weight comes from calibre's imports and Qt, not the language. The tray talks to the host over HTTP, so this can be revisited if a large library turns out slow.

## Open questions

- **Path A or B.** `calibre-server` only serves. Every other feature lives in GUI code that assumes the main window (`Main`) exists.
  - **A. Lean host.** Start from calibre's server parts and add each feature as zen code. It stays near 100 MB. Auto-add is easy, news is moderate, and device sync is hard (wireless only in Docker). Interface-action plugins never work.
  - **B. Invisible GUI host.** Run the real `Main` offscreen with its embedded server, as `src/calibre_zen/tests/test_gui.py` already does. Everything works on day one, and it costs about 280 MB.
- **Mini's window.** A plain Qt window, calibre's own `Application` with the zen look, or a native shell around the system web view. This decides most of Mini's weight. It can wait until headless works.
- **The first slice**, which is the same under A or B. Approved 2026-10-08 as a first cut, on path A:
  1. A `zen-host` entry point that owns the library. It runs the server with the GUI's Sharing settings and closes idle libraries.
  2. A status endpoint for libraries, jobs and uptime, through calibre's content-server plugin hook (`srv/handler.py:221`).
  3. A menubar and tray process. It starts and stops the host, shows status, toggles settings, and hands the library over when the full GUI opens.

## Measurements

macOS 15.7 on an Apple M3 Max with 14 cores, calibre.app 9.15 matching the source tree. The library is `.calibre-zen/perf-library`, which holds 2,000 books. The scripts are in [`measure/`](measure/) and print every process.

**Footprint** is the dirty memory Activity Monitor shows as "Memory", from `footprint(1)`. RSS is also printed, but it counts the shared Qt frameworks once per process and drops when macOS compresses pages, so footprint is the number to compare.

### The whole app, idle

| What | Footprint | Processes | Threads | Start |
|---|---|---|---|---|
| Full zen GUI, 30 s after launch | **608 MB** | 8 | 71 | about 30 s |
| The same in develop mode | 619 MB | 8 | 71 | |
| Full GUI with no spare reader and no update check | **278 MB** | 3 | 18 | |
| `calibre-server`, stock | **94 MB** | 2 | 16 | 1 s |
| The same, after the first page of books and 30 cover thumbnails | 119 MB | 2 | 24 | |
| `calibre-server` in develop mode | 458 MB | 3 | 55 | 12 s |

The full GUI's 608 MB, by process:

| Process | Footprint |
|---|---|
| The GUI itself | 232 MB |
| The spare reader | 180 MB |
| A book-render worker the spare reader keeps ready | 73 MB |
| Two QtWebEngine renderers, for the spare reader | 13 + 53 MB |
| Three small `calibre-parallel` workers | about 19 MB each |

All of these are idle at 0% CPU.

### Building blocks, idle

| What | Footprint | Threads |
|---|---|---|
| A Go binary with `net/http` and one `/status` route | **3 MB** | 5 |
| calibre's Python interpreter, nothing imported | 31 MB | 3 |
| A plain `QApplication` with a tray icon and a five-item menu | 37 MB | 3 |
| A plain Qt window listing every book's title | 47 MB | 11 |
| One library open with calibre's database layer, no Qt, no server | 77 MB | 7 |
| calibre's own `Application` with the zen look, the same title list | **156 MB** | 6 |

Every calibre process that imports enough of calibre also starts a small `safe_atexit` worker of 14 to 20 MB. It is included above.

A plain Qt window holding all 1,942 covers as 100×150 tiles measured 52 MB in one run and 183 MB in another. macOS accounts for pixmap memory unevenly. A real view loads only the covers on screen, so the bare title list is the floor that counts.

### One question, three ways

The question is "list one book".

| How | Time | Peak RSS |
|---|---|---|
| `calibredb`, opening the library itself | 0.23 to 0.30 s | 98 MB |
| `calibredb --with-library http://…` through a running server | 0.17 to 0.29 s | 76 MB |
| One HTTP request to the running server | 0.003 s | |

### Opening and searching the library

The same 2,000 books, with calibre's database layer in calibre's own Python.

| What | Time |
|---|---|
| Open the library and load it into memory | 0.04 to 0.10 s |
| Raw SQLite read of every row of all 68 tables, plain Python | 0.04 s |
| Search `tag:fiction or author:a` | 5 to 9 ms |
| Sort every book by title | 3 ms |

### The same tiny server in seven languages

Each is an HTTP server with one `/status` route, using only the standard library, idle after 100 requests. The script is `measure/measure-languages.sh`.

| Language | Footprint | First answer | What ships |
|---|---|---|---|
| Rust 1.98, hand-written, one request at a time | under 1 MB | 0.05 s | 352 KB binary |
| Swift 6.1, Darwin sockets | under 1 MB | 0.02 s | 56 KB binary, Apple only |
| Go 1.25, `net/http` | 4 MB | 0.03 s | 5 MB binary |
| Bun 1.2, compiled | 9 MB | 0.09 s | 55 MB binary |
| Python 3.14, `http.server` | 13 MB | 0.19 s | script, plus Python |
| Node 22 | 16 MB | 0.10 s | script, plus 104 MB Node |
| Java 23, default JVM | 37 MB | 0.12 s | class, plus a 338 MB JVM |

Plain Python idles at 13 MB. calibre's interpreter starts at 31 MB before anything is imported, so most of a calibre process's weight is calibre and Qt, not the language.

### What the numbers say

- **The spare reader is more than half the full GUI.** Without it the GUI drops from 608 to 278 MB. That is the realistic floor for path B.
- **A served library costs about 100 MB** with today's server. This is the starting point for path A.
- **calibre's `Application` adds about 110 MB** to a bare Qt window, through calibre's imports, fonts, plugins and the zen hooks. A Mini window that wants to be light should carry the zen look without it.
- **Opening the library costs about what reading the raw SQLite file costs.** On 2,000 books there is no slow path to rewrite.
- **Starting a calibre process for each command is slow and heavy**: a quarter-second and about 100 MB each time. A host that dispatches work should keep one Python process warm and talk HTTP to it. A request then takes 3 ms.
- **Develop mode inflates the server** by about 360 MB and 11 s, because it rebuilds the web app in QtWebEngine on every start (`srv/standalone.py:83`). Packaged builds turn develop mode off (`constants.py:446`), so they match the stock row.
- **Not yet measured:**
  - A library of tens of thousands of books. Dropped from phase 0; 2,000 books is the working size.
  - The host with auto-add, news and devices running.

## Phase 0: load and Linux

Run on 2026-10-08. Many clients use one `calibre-server` at once, the way the web app and Mini would: searches, pages of books, single books, cover thumbnails, the tag browser and small writes. Each level runs for 15 s. The load generator is [`measure/load.py`](measure/load.py), which uses only the standard library.

### Two bugs in calibre's server

Both are in calibre 9.15 and in upstream `master` as of `ff944d981b` (2026-10-08). Both show up with a handful of users, before any zen code is involved.

**1. Concurrent reads fail with HTTP 500.** From 4 clients up, a few percent of page and book requests fail with `apsw.ThreadingViolationError: Cursor couldn't run because the Connection is busy in another thread`.
- Reading a book's notes queries SQLite while holding only the *read* lock: `srv/metadata.py:101` → `db/cache.py:789` (`items_with_notes_in_book`) → `db/backend.py:1110` → `db/notes/connect.py:320`.
- The read lock lets many threads in at once, but they all share one apsw connection, which allows one cursor at a time.
- The web app calls this for every page of books (`/interface-data/get-books`) and every book (`/interface-data/book-metadata`).

**2. Reads and writes together can deadlock the whole server for good.** At 32 clients with 5% writes the server stops answering, uses 0% CPU, and ignores SIGTERM. A thread dump taken with `faulthandler` shows a lock-order inversion:

| Thread | Holds | Waits for |
|---|---|---|
| The event loop, rendering the tag browser lazily (`srv/code.py:682` → `srv/handler.py:153`) | the handler's cache lock | the library's read lock |
| A worker writing a rating (`srv/cdb.py:250`) | nothing | the library's write lock |
| A worker serving a page of books (`srv/code.py:611` → `srv/handler.py:180`) | the library's read lock | the handler's cache lock |

- The library's lock makes new readers wait while a writer waits, so the event loop cannot get its read lock.
- The writer waits for the page-of-books worker to let go, and that worker waits for the event loop.
- The event loop is the thread that does all network I/O and handles signals, so nothing gets through, not even SIGTERM.
- `get-books` takes the read lock then the cache lock. The tag browser takes the cache lock then the read lock. Either order alone is fine. Together, with a waiting writer, they are a cycle.

### Throughput on this Mac

| Clients | Reads only | p95 | Server CPU | With 5% writes | p95 |
|---|---|---|---|---|---|
| 1 | 140 req/s | 10 ms | 81% | 67 req/s | 146 ms |
| 4 | 578 req/s | 26 ms | 99% | 75 req/s | 213 ms |
| 16 | 583 req/s | 88 ms | 101% | 43 req/s | 663 ms |
| 32 | 552 req/s | 126 ms | 96% | deadlocked | |

Memory stayed at 111 to 132 MB footprint throughout. Errors are bug 1, at 1 to 7% of page and book requests from 4 clients up.

### Linux in Docker

Docker Desktop's VM on this Mac: 1 CPU and about 1 GB of RAM, shared with three other containers that were already running. Stock calibre 9.14 for Linux arm64 on `ubuntu:24.04`, as [`measure/docker/Dockerfile`](measure/docker/Dockerfile) builds it.

| What | Value |
|---|---|
| Image | 388 MB compressed, 1.41 GB on disk |
| Launch to first answer | 1 s |
| Idle, server and its one worker | 135 MB PSS |
| After the first page and 30 thumbnails | 188 MB PSS |
| After the load below | 213 MB PSS |

| Clients, reads only | Throughput | p95 |
|---|---|---|
| 1 | 70 req/s | 57 ms |
| 4 | 154 req/s | 95 ms |
| 16 | 175 req/s | 208 ms |

The image needs `tzdata` beside the GL, font and NSS libraries: calibre's Linux build reads time zones from the system, and fails at import without them.

### What phase 0 says

- **One host process tops out at one CPU core.** Reads level off near 580 requests a second on the M3 Max and 175 on the Docker VM's single core, with the server at 100% of one core. That is Python's GIL. It is far more than a household or a Mini window needs.
- **Writes are the weak spot, not reads.** 5% writes cut throughput by about eight times at 4 clients, and CPU drops to about 80%. The server is waiting, not working. A likely cause, not yet confirmed: each write clears the search and tag-browser caches, so the next readers redo that work.
- **Both bugs must be dealt with before a server ships.** A headless host with auto-add, Mini adding books and a few browsers open is exactly the mix that triggers them.
- **Linux is a fine target.** It starts in a second, idles at 135 MB, and runs on a single core with room to spare.

## First cut

Built on 2026-10-08 on `wt/headless`, against the contract in [first-cut.md](first-cut.md). Path A: the host is calibre-server with zen's parts added from outside, and both server bugs are worked around in zen's own process.

| What | Result |
|---|---|
| Tests | 275 pass, including 21 for the host, 33 for the tray and 12 that reproduce both server bugs |
| Host on this Mac, 32 clients, 5% writes | 52 req/s, 0 errors, no hang, answers in 13 ms afterwards, stops cleanly |
| The same load on stock calibre-server | deadlocks for good |
| Host on the Docker VM, 32 clients, 5% writes | 58 req/s, 0 errors, no hang, exit 0 on `docker stop` |
| Host memory, dev library, browsed | about 130 MB footprint, plus an 18 MB helper |
| Tray memory | about 40 to 60 MB footprint |
| Image | 424 MB compressed, 1.55 GB on disk, healthy in 1 s |
| Auto-add in Docker | a dropped file became a book within seconds, and the file was removed |

Running calibre's Python from `src/` costs about 20 MB over the bundle's frozen copy, measured on stock calibre-server (111 MB against 130 MB footprint). A package pays it too.

## Running the measurements

```sh
docs/plans/modes/measure/measure-server.sh
MEASURE_DEVELOP=1 docs/plans/modes/measure/measure-server.sh
docs/plans/modes/measure/measure-gui.sh packaged
docs/plans/modes/measure/measure-gui.sh lean
docs/plans/modes/measure/measure-floors.sh
docs/plans/modes/measure/measure-floors.sh go db qt-tray
docs/plans/modes/measure/measure-languages.sh
docs/plans/modes/measure/measure-load.sh
MEASURE_WRITES=0 docs/plans/modes/measure/measure-load.sh 1 4 16 32
MEASURE_WRITES=0 docs/plans/modes/measure/measure-docker.sh .calibre-zen/upstream/calibre-9.14.0-arm64.txz 1 4 16
```

The load scripts work on a throwaway copy of the library, so its ratings stay as they are. `measure-docker.sh` needs Docker and a calibre Linux `.txz` for the VM's architecture. The others are macOS only, and they need `/Applications/calibre.app` and the perf library. `MEASURE_LIBRARY` points them at another library. The GUI script refuses to run while a calibre-zen window is open. The server cannot run beside a GUI either, because both take the same lock.

## What calibre already has

### The one rule

Calibre allows one process per library per user, enforced by a single-instance lock named `db`. The GUI (`gui2/main.py:446`), `calibre-server` (`srv/standalone.py:177`) and local `calibredb` (`db/cli/main.py:163`) all take it, and the second one to start refuses.

- The lock name comes from `__appname__`. Upstream calibre and calibre-zen therefore do not see each other's lock.
- On Linux the lock is an abstract socket, which a Docker container does not share with its host.

### calibre-server

The code is in `srv/standalone.py`, with options in `srv/opts.py`.

- It serves many libraries and opens each one on first use (`library_broker.py:123`). It never closes them. The GUI's broker closes idle ones after 300 s (`:303`).
- It builds a headless `QApplication` to draw covers (`standalone.py:249`), so it needs Qt. It does not need X.
- It ignores `server-config.txt`, the file the GUI's Sharing preferences write. Only the embedded server reads it (`srv/embedded.py:53`).
- `--daemonize` works only on Linux.
- It has no health or status endpoint, and `JobsManager` has no public list of jobs.
- **Writes** are add, delete, set-fields, set-cover, convert and annotations (`srv/cdb.py`). They need one of these:
  - a logged-in user who is not read-only;
  - `local_write` from localhost;
  - an address in `trusted_ips`.
- `calibredb --with-library http://…` uses the same write endpoints.
- **It starts:**
  - an HTTP thread pool of 10;
  - BonJour;
  - a jobs loop, with a `calibre-parallel` worker per job;
  - for each library, a page-count thread, plus an FTS pool when full-text search is on.

### The GUI in the background

- **Tray support exists.** There is a tray icon (`config['systray_icon']`, off by default), `--start-in-tray` and hide-on-close (`gui2/ui.py:293-324,1576`). The tray menu has Show/Hide, Eject, Restart and Quit.
- **A hidden window keeps everything running:**
  - device probing every 2 s;
  - metadata backup every 2 s;
  - an IPC poll every 0.2 s;
  - the news scheduler every minute;
  - the GUI's worker pool;
  - the spare reader.
- **Nothing hides the Dock icon.** `calibre_zen/reader/activation.py` already can.
- **The GUI's socket is one-way** (`gui2/listener.py`), so nothing can ask the GUI a question.

### Features that need the main window

- **Auto-add:** `gui2/auto_add.py:221` returns early without a GUI.
- **News:** the `Scheduler` calls `get_gui()` to download and add (`gui2/dialogs/scheduler.py:710`).
- **Devices:** the `DeviceManager` thread stands alone (`gui2/device.py:181`). What happens when a device connects lives in `DeviceMixin`, which is wired to `Main`.
- **Plugins:** interface-action plugins need `Main` by definition. Metadata, file-type, device and content-server plugins do not.

### Parts Mini can reuse

- **These work without `Main`:**
  - `LibraryDatabase` and `Cache`;
  - `BooksModel`, which starts `MetadataBackup`;
  - `GridView`, nearly;
  - `Adder` (`gui2/add.py`), where only auto-convert needs the GUI;
  - the spare reader's `Spare.hand_off` (`calibre_zen/reader/spare.py`).
- **These are tied to `Main`:** `BooksView`, book details, Quickview and the overlay's `centre/` widgets.
- **Annotations need a route.** The reader reports them through `save-annotations:` on the GUI socket. With no listener it writes to `metadata.db` directly (`gui2/viewer/integration.py:110`). As a client, Mini must send these through the host.

### Picking a mode at launch

- **No upstream edit is needed.** Wrap `GuiRunner.start_gui` (`gui2/main.py:291`) from `hooks.py`, driven by an environment variable or a gprefs key, the way `features.py` does.
- **A `--mini` flag has to be stripped first,** in the launchers or `bootstrap.py`. Calibre's option parser rejects unknown flags (`main.py:142`).
- **Per-mode launchers fit the packaging.** The Windows launcher already builds one exe per target (`ZEN_TARGET`), and the Linux package has `wrap()`.

### Docker

- **Upstream ships no Dockerfile.** `manual/server.rst:362-410` covers systemd, socket activation, a reverse proxy and `--manage-users`.
- **The image people use** is [linuxserver/calibre](https://hub.docker.com/r/lsiodev/calibre). It streams the full GUI over KasmVNC, and users call it heavy and hard to use on a phone.
- **Others run the server alone.** See [calibre-server in a container](https://www.bentasker.co.uk/posts/blog/general/containerising-and-deploying-calibres-content-server-to-allow-web-annotations.html) and [docker-calibre-headless](https://github.com/cartfisk/docker-calibre-headless).
