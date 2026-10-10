# When a launch cannot reach the running copy

Noted 2026-10-10, while adding Restart in headless mode (PR #25). Deferred: the fixes below add more than they are worth until people report these. Come back here when they do.

## The symptom

Something holds calibre's single-instance lock, but a new launch cannot reach it or cannot get the library. The person sees one of:

- "Contacting calibre failed. Failed to contact running instance of calibre, try restarting calibre."
- Nothing at all: the click opens no window.
- "Another calibre program ... is already running", from a window opened while something else holds the library.

It happened once during development. The test suite opened calibre's real window under the same name as a running dev window, took over its socket and deleted it on the way out. That cause is fixed (`tests/main.py`, `isolate_ipc`).

## Ways it can still happen

| # | How | What they see | How likely |
|---|---|---|---|
| 1 | Opening the app while the last window is still quitting. `Main.shutdown` closes the socket partway through, and the process can take seconds more (jobs, devices, threads) to let go of the lock. | Nothing opens if the old one finishes within 6 s (calibre's `send_message` gives up quietly), else "Contacting calibre failed" | Most likely. Upstream calibre has it too. Restart in headless mode and quick reopens make it a little more common |
| 2 | The window's socket file is deleted while it runs. On macOS it is `/tmp/calibre-zen-<uid>-gui.sock`. Cleanup apps that empty `/tmp` can do it. This macOS has no periodic `/tmp` cleaner, and Linux uses an abstract socket with no file | Every launch and "Open with" fails until the window is quit | Rare |
| 3 | The tray's socket is deleted. `QLocalServer` puts it in `QDir.tempPath()`, which is `/var/folders/.../T` on macOS and `/tmp` on Linux, and both can be cleaned of old files. A tray that runs for weeks could lose it | Messages fall back to the lock, which is fine. But a window opened from the Dock cannot ask for the library back, and gets "Another calibre program ... is already running" | Possible, for people who leave the tray running |
| 4 | A window hangs while quitting and never exits | As 1, forever, with no hint what to do | Rare |

Not a user problem: running from source and a packaged copy at once. Both are `calibre-zen`, so they share one lock and the second hands its arguments to the first.

## How this is usually solved

The thing that says "I'm running" and the thing other launches talk to are one object, owned by the operating system, and gone when the process dies. Then "lock held, nobody answering" cannot happen, a crash leaves nothing behind, and a cleanup tool cannot delete it.

- **Linux:** a D-Bus name (GApplication, KDBusService), or an abstract socket, which calibre already uses there.
- **Windows:** a named mutex and a named pipe, both kernel objects.
- **macOS:** LaunchServices keeps one copy of an app opened from the Dock or Finder, and reopen and open-file arrive as Apple Events. Socket files matter only when the binary is run directly, as the tray and the dev launcher do.
- **Browsers** add two rules on top of a lock and a socket. The running copy must answer within a timeout, and with no answer the new one checks whether the lock holder is alive. Firefox then says it is "already running, but is not responding". Chromium kills a copy that is truly hung.
- **Menubar helpers** let the service manager own the endpoint: a launchd agent with a Mach service, systemd socket activation, D-Bus activation. That also gives start at login and a restart after an update.

calibre on macOS keeps the lock (a `lockf` file) and the socket (a file in `/tmp`) apart, does not wait for an answer, and gives up instead of opening when the old copy quits.

## What to do, in order, when it is worth it

1. **Put the tray's socket where nothing cleans it.** Linux: `QLocalServer.SocketOption.AbstractNamespaceOption`, which calibre 9.15's Qt (6.10.1) has. Windows: already a pipe. macOS: a short path in the app's own folder, falling back to the temp folder if it would pass the 104-byte socket path limit. Fixes 3.
2. **The same for the window's socket on macOS.** One line in `src/calibre/utils/ipc/__init__.py`, which already carries a fork-identity hunk. It changes behaviour against upstream, so decide first whether it counts as identity. Fixes 2.
3. **The browser rules at launch**, by wrapping `calibre.gui2.main.communicate`. Wait for an answer. If the old copy is quitting, wait for it and then open a fresh window. If it is alive and silent for about 20 s, say so plainly and offer Force quit. Fixes 1 and 4 on Windows and Linux. On macOS a Dock click may never start a new process, so the quitting copy would have to notice the reopen itself.
4. **Later, its own project:** the tray under the service manager on each platform. Brings start at login and a restart after updates with it.

Trade-offs to weigh then:

- 1 and 2 are small and remove a whole class of failure.
- 3 adds the most coupling to calibre's startup code: another wrap with a drift test. A bug there could stop the app opening, so it must fall back to calibre's own behaviour on any error.
- Force quit can leave a cover or a backup file half written. `metadata.db` survives. It needs a polite stop first, a check that the pid is really ours, and a confirmation. Windows cannot tell which process holds a mutex, so there it can only explain.
- A watchdog that recreates a missing socket was considered and dropped: it treats the symptom, leaves launches failing until its next check, and runs a timer forever.

## Related, also deferred

When the app updates itself while the tray runs, the old tray keeps running code from the replaced app. The updater should restart the tray too.
