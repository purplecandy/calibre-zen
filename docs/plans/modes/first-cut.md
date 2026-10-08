# Headless: the first cut

The contract four pieces of work build against. Each piece lives on its own `wt/headless-*` branch and is merged into `wt/headless`. Path A from [README.md](README.md): a lean host built from calibre's server parts, all Python.

## What a person gets

- **`./calibre-zen --headless`.** A menubar icon on macOS, a tray icon elsewhere, with no Dock icon and no window. It starts the host, shows whether sharing is on and at what address, and offers a few toggles.
- **`./calibre-zen --host`.** The host alone, in the foreground. This is what Docker runs.
- **A Docker image** that runs the host on a mounted library, with an optional auto-add folder.

## The pieces

| Piece | Branch | Owns |
|---|---|---|
| Server fixes | `wt/headless-fixes` | `src/calibre_zen/host/fixes.py`, the one-line call in `src/calibre_zen/hooks.py`, `src/calibre_zen/tests/test_srvfix.py` |
| Host | `wt/headless-host` | everything else in `src/calibre_zen/host/`, the `--host` and `--headless` flags in `./calibre-zen`, `src/calibre_zen/tests/test_host.py` |
| Tray | `wt/headless-tray` | `src/calibre_zen/tray/`, `src/calibre_zen/tests/test_tray.py` |
| Docker | `wt/headless-docker` | `packaging/docker/`, and any Linux packaging change it needs |

Nobody else edits a file another piece owns. `src/calibre_zen/README.md` and `docs/plans/modes/README.md` are written at merge time, from each piece's report.

## Interfaces

### `calibre_zen.host.fixes`

- `install() -> None`. Patches calibre's server from outside so both bugs in [upstream-bugs.md](upstream-bugs.md) are gone. Safe to call more than once, and cheap, because the GUI calls it at start for its embedded server.
- No upstream file changes.

### `calibre_zen.host` command line

```sh
calibre-debug -e src/calibre_zen/host/__main__.py -- [options] [LIBRARY ...]
```

- `calibre_zen.host.main.main(argv: list[str] | None = None) -> int` does the work. `__main__.py` only calls it.
- **Options are calibre-server's own**, from `calibre.srv.standalone.create_option_parser`, so `--port`, `--listen-on`, `--enable-auth`, `--userdb`, `--enable-local-write`, `--trusted-ips`, `--url-prefix` and the rest all work.
- **Defaults come from the GUI's Sharing settings** (`calibre.srv.opts.server_config()`, the file `server-config.txt`) instead of calibre-server's built-in defaults. A flag on the command line wins.
- **Extra options:** `--auto-add DIR` watches a folder and adds what lands in it. Without it, the GUI's own auto-add folder is used if one is set (`gprefs['auto_add_path']`). `--no-auto-add` turns it off.
- **Libraries:** as calibre-server. With none given, the GUI's libraries.
- **Takes the same single-instance `db` lock** as calibre-server and the GUI. If the lock is held, it exits with status **3** and a one-line message, so the tray can tell "calibre-zen's window is open" from a crash.
- SIGTERM stops it cleanly. So does `POST /zen/stop`.
- `calibre_zen.host.fixes.install()` runs before the server is built.

### `calibre_zen.host.launch`

For any zen process that wants to run the host as a child: the tray now, the GUI later.

- `start(args: list[str], log_path: str | None = None) -> subprocess.Popen`. Starts the host the way `calibre_zen/reader/spare.py` starts a spare reader: calibre's own worker executable with `CALIBRE_SIMPLE_WORKER`. The arguments travel in the environment as JSON in `CALIBRE_ZEN_HOST_ARGS`. On macOS the child gets no Dock icon. Works from a source tree and from a package.
- `local_url(args: list[str] | None = None) -> str`. `http://127.0.0.1:<port><url_prefix>` for the host those arguments would start, after the Sharing defaults.
- `status(base_url: str, timeout: float = 2) -> dict | None`. `GET /zen/status`, or `None` if nothing answers.
- `stop(base_url: str, timeout: float = 10) -> bool`. `POST /zen/stop`, then waits for the port to close.

### `GET /zen/status`

JSON. Answers without a login when the request comes from the same machine. From anywhere else it follows the server's normal auth rules.

```json
{
  "app": "calibre-zen",
  "version": "0.3.0",
  "calibre": "9.15.0",
  "pid": 12345,
  "started": "2026-10-08T21:00:00+00:00",
  "uptime": 3600.5,
  "port": 8080,
  "url_prefix": "",
  "urls": ["http://192.168.1.18:8080/"],
  "auth": false,
  "local_write": true,
  "libraries": [
    {"id": "Calibre_Library", "name": "Calibre Library", "path": "/Users/x/Calibre Library", "open": true, "books": 2000}
  ],
  "jobs": {"running": 0, "waiting": 0},
  "auto_add": {"folder": "/Users/x/Add to calibre", "added": 3, "failed": 0, "last": "2026-10-08T21:30:00+00:00"},
  "memory_mb": 112.4
}
```

- `books` is `null` for a library that has not been opened yet. Opening one only to count it is not worth the memory.
- `auto_add` is `null` when no folder is watched.
- `urls` are the addresses a phone on the same network would use.

### `POST /zen/stop`

Same machine only; 403 from anywhere else. Answers `{"stopping": true}` and then shuts the server down.

### `calibre_zen.tray`

```sh
calibre-debug -e src/calibre_zen/tray/__main__.py -- [--library PATH] [host options]
```

- `calibre_zen.tray.main.main(argv=None) -> int`.
- A plain `QApplication`, not calibre's `Application`, to stay light. No Dock icon on macOS.
- Starts the host with `launch.start`, polls `launch.status` every few seconds, and shows the state in the menu.
- **Menu**, top to bottom:
  - A state line: "Sharing at 192.168.1.18:8080", "Starting…", "Paused while calibre-zen is open", or "Stopped: <reason>".
  - The library name and book count.
  - **Open in browser.** **Copy address.**
  - **Open calibre-zen.** Hands the library over: stop the host, start the full app, and start the host again when the app quits.
  - Toggles: **Share on this network** (listen on all addresses, or this computer only), **Allow changes from this computer** (`local_write`), **Add books from a folder…** (chooses or clears the auto-add folder). Changing one writes the Sharing settings and restarts the host.
  - **Quit.** Stops the host, then the tray.
- If the host exits with status 3, the full app is open. The tray says so and tries again every 10 seconds.

### `./calibre-zen`

- `./calibre-zen --host [options]` runs the host in the foreground, on the same library the GUI would open.
- `./calibre-zen --headless [options]` runs the tray, which starts the host on that library.
- Both are stripped before calibre's own option parser sees them.

## Rules for every piece

- **No upstream edits.** Nothing under `src/calibre/` changes. Patches happen from outside, at run time, as the rest of the overlay does.
- **No bare `assert`.** The bundle runs `-OO`. Use `if …: raise`.
- **Lint:** `uvx ruff check src/calibre_zen && uvx ruff format src/calibre_zen`.
- **Tests run with** `./zen-test <module>`. Run your own module while working. Tests must not take the global single-instance lock, because other pieces run their tests at the same time. Set `CALIBRE_NO_SI_DANGER_DANGER` or call below the lock. Use a random free port.
- **Commits** end with `Co-authored-by: Nadeem Siddique <nadeem@kibibyte.in>`. Commit on your branch. Never push.
- **Nothing on screen.** No screenshots, no clicks, no typing into other apps. Everything runs offscreen.

## Trying it

Everything below has passed offscreen. The menubar itself has not been tried, because nothing here may draw on a screen someone is using.

### The menubar

From the repo root, with no calibre-zen window open:

1. Run `./calibre-zen --headless`. A books icon appears in the menubar. There is no Dock icon and no app menu.
2. Open the menu. It says "Starting…", then "Sharing at <address>", and the library with its book count.
3. Open in browser shows the library. Copy address, then paste it on a phone on the same Wi-Fi.
4. Turn off Share on this network. The state says 127.0.0.1, and `.calibre-zen/config/server-config.txt` holds `listen_on 127.0.0.1`. Turn it back on.
5. Turn on Allow changes from this computer.
6. Choose Add books from a folder…. **Check that the folder dialog comes to the front with the keyboard.** Pick a folder, then uncheck the item to clear it.
7. Choose Open Calibre Zen. **Check that the window opens and comes to the front.** The menu says Paused and the switches are greyed out. Quit the window, and sharing comes back about 10 s later. The tray waits so a restarting app gets the library first.
8. Kill the host's `calibre-parallel` process. The menu says Sharing stopped, with the reason and Try again. It starts again by itself after about 5 s.
9. Switch macOS between light and dark. The icon follows.
10. Run `./calibre-zen --headless` again. It says the menubar app is already running and exits.
11. Choose Quit. The icon and the host are both gone, and nothing listens on the port.

### The host alone

```sh
./calibre-zen --host --port 8090
curl -s http://127.0.0.1:8090/zen/status
curl -s -X POST http://127.0.0.1:8090/zen/stop
```

### Docker

calibre 9.15's Linux build has not been downloaded on this machine. Until it is, the image builds from the cached 9.14 installer, which is fine for a try but not for a release:

```sh
mkdir -p /tmp/zen-upstream && cp .calibre-zen/upstream/calibre-9.14.0-arm64.txz /tmp/zen-upstream/
docker build -f packaging/docker/Dockerfile --build-context upstream=/tmp/zen-upstream \
  --build-arg UNPINNED_TARBALL=calibre-9.14.0-arm64.txz -t calibre-zen .
docker run --rm -p 8080:8080 -e PUID=$(id -u) -e PGID=$(id -g) \
  -v "$PWD/.calibre-zen/library:/library" -v /tmp/zen-config:/config calibre-zen
```

Without the two `upstream` arguments, the build downloads and checks the pinned 9.15 release itself.

## After the first cut

Everything above is merged on `wt/headless`, with 306 tests passing. A review found 13 problems at the edges between processes, and all 13 are fixed.

### Decisions for the owner

- **Download calibre 9.15's Linux build.** The image is meant to build from the pinned release, about 190 MB per architecture. It has only been built from the cached 9.14 installer so far.
- **Push `wt/headless` and open the pull request.** A draft description is ready.
- **How far to trust "this computer".** A proxy on the same machine that rewrites `Host` to 127.0.0.1 and adds no forwarding header makes every visitor look local. nginx's plain `proxy_pass` does this. Those visitors could then read `/zen/status`, which includes paths, and call `/zen/stop`. One fix is a secret written to a file only the owner can read, which the tray sends with stop. Another is to document it.
- **The library's name in Docker.** A new library at `/library` shows up as "library" in the web app.
- **Publishing the image.** No workflow builds or publishes it yet. The Docker README says what it is called once published.

### Known gaps

- **Writes are slow under load.** About 50 to 90 requests a second with 5% writes, against about 600 for reads alone. Each write probably clears the search and tag-browser caches. Not yet measured.
- **The tag browser still renders on the server's event loop.** It can no longer deadlock, but the whole server waits while a write holds the lock.
- **Inside Docker, `/zen/status` lists the container's own address**, which a phone can't use.
- **Idle libraries are never closed**, as with calibre-server.
- **Auto-add can't ask.** A duplicate or a failed file stays in the folder, and there is no auto-convert.
- **Memory.** The host is about 20 MB heavier than stock calibre-server. Running calibre's Python from `src/` costs about another 20 MB, and every packaged process pays that.
- **Not tried yet:**
  - the real menubar;
  - Windows and Linux trays, including the Windows lock probe;
  - amd64 and a two-platform image;
  - a library of tens of thousands of books.
- **One flaky failure.** In a single test run, with other test runs going at the same time, a host died with a segfault before writing anything. Three later runs passed.
- **Mini mode** has not been started.
