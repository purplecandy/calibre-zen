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

## Open questions

- **Path A or B.** `calibre-server` only serves. Every other feature lives in GUI code that assumes the main window (`Main`) exists.
  - **A. Lean host.** Start from calibre's server parts and add each feature as zen code. It stays near 100 MB. Auto-add is easy, news is moderate, and device sync is hard (wireless only in Docker). Interface-action plugins never work.
  - **B. Invisible GUI host.** Run the real `Main` offscreen with its embedded server, as `src/calibre_zen/tests/test_gui.py` already does. Everything works on day one, and it costs about 280 MB.
- **What the host is written in.** A small supervisor in another language (Go, say) could own the menubar icon, the process lifecycle and the HTTP front door, and hand work to calibre's Python. Everything that is calibre itself stays Python: the database layer, metadata readers, conversion, recipes, device drivers and plugins. The numbers below show what each layer costs.
- **The first slice**, which is the same under A or B. Not yet approved:
  1. A `zen-host` entry point that owns the library. It runs the server with the GUI's Sharing settings and closes idle libraries.
  2. A status endpoint for libraries, jobs and uptime, through calibre's content-server plugin hook (`srv/handler.py:221`).
  3. A menubar and tray process. It starts and stops the host, shows status, toggles settings, and hands the library over when the full GUI opens.

## Measurements

macOS 15 on Apple silicon, calibre.app 9.14 matching the source tree. The library is `.calibre-zen/perf-library`, which holds 2,000 books. The scripts are in [`measure/`](measure/) and print every process.

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

### What the numbers say

- **The spare reader is more than half the full GUI.** Without it the GUI drops from 608 to 278 MB. That is the realistic floor for path B.
- **A served library costs about 100 MB** with today's server. This is the starting point for path A.
- **calibre's `Application` adds about 110 MB** to a bare Qt window, through calibre's imports, fonts, plugins and the zen hooks. A Mini window that wants to be light should carry the zen look without it.
- **Starting a calibre process for each command is slow and heavy**: a quarter-second and about 100 MB each time. A host that dispatches work should keep one Python process warm and talk HTTP to it. A request then takes 3 ms.
- **Develop mode inflates the server** by about 360 MB and 11 s, because it rebuilds the web app in QtWebEngine on every start (`srv/standalone.py:83`). Packaged builds turn develop mode off (`constants.py:446`), so they match the stock row.
- **Not yet measured:**
  - Linux, which is the Docker target.
  - A library of tens of thousands of books.
  - The host with auto-add, news and devices running.

### Running them

```sh
docs/plans/modes/measure/measure-server.sh
MEASURE_DEVELOP=1 docs/plans/modes/measure/measure-server.sh
docs/plans/modes/measure/measure-gui.sh packaged
docs/plans/modes/measure/measure-gui.sh lean
docs/plans/modes/measure/measure-floors.sh
docs/plans/modes/measure/measure-floors.sh go db qt-tray
```

They are macOS only, and they need `/Applications/calibre.app` and the perf library. `MEASURE_LIBRARY` points them at another library. The GUI script refuses to run while a calibre-zen window is open. The server cannot run beside a GUI either, because both take the same lock.

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
