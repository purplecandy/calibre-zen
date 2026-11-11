# calibre's web app today

Surveyed 2026-10-11 on calibre 9.15. The fork has changed none of it: `src/pyj` and `src/calibre/srv` are identical to upstream `v9.15.0`.

## How it is built

- **Language.** RapydScript-ng, a Python-like language that compiles to JavaScript. About 40k lines in `src/pyj`: `book_list/` is the library (14.5k), `read_book/` is the reader (19.5k), the rest is shared helpers.
- **No npm, no TypeScript, no bundler.** The compiler ships inside calibre as `resources/rapydscript/compiler.js.xz` and runs in QtWebEngine (`src/calibre/utils/rapydscript.py`).
- **One file out.** `compile_srv()` compiles `src/pyj/srv.pyj` and inlines it, `reset.css`, `base.css` and an SVG icon sprite (`imgsrc/srv/*.svg`) into `resources/content-server/index.html`. The result is a single 3.9 MB `index-generated.html`. There is no code splitting.
- **Served as a file.** `srv/code.py` sends `index-generated.html` as is, without a login check. The page carries no data. It asks `/interface-data/update` for everything once it starts.

### When it is compiled

| Where | What happens |
|---|---|
| `./calibre-zen`, then Connect/share | develop mode: `srv/embedded.py` recompiles on every server start |
| `./calibre-zen --host` | recompiles only when a source is newer than the compiled file (`host/main.py`, `web_app_is_current`) |
| `calibre-server --auto-reload` | recompiles and reloads the browser on every save (`srv/auto_reload.py`) |
| Packaged app and Docker | never. `CALIBRE_ZEN_PACKAGED=1` turns develop mode off, and upstream's prebuilt `index-generated.html` in the binary's `resources/` is served |

Packaging copies tracked files we changed under `resources/` over the binary's. `index-generated.html` is gitignored, so a changed web app never reaches an installer today.

## How it renders

- **DOM by hand.** About 1,500 `E.div(...)` calls (RapydScript's `elementmaker`) and helpers in `dom.pyj`. No virtual DOM, no templates. Every navigation clears the panel and rebuilds it.
- **Routing in the hash.** `#panel=...&library_id=...`, through the History API (`book_list/router.pyj`, `book_list/ui.pyj`). Two modes, the book list and the reader. A module registers a panel with `set_panel_handler`.
- **State in module globals.** `book_list/globals.pyj`, `library_data.pyj`. No store, no reactivity.
- **CSS three ways.** `base.css` and `reset.css`, about 380 `build_rule` strings inside the modules, and inline styles. Colours are `--calibre-color-*` variables (`book_list/theme.pyj`), light and dark, following the system or a setting. Phone layouts are about 26 `@media` blocks spread across modules.
- **Almost no libraries.** MathJax is fetched on demand and kept in IndexedDB. No PDF viewer.
- **Network.** Callback `XMLHttpRequest` in `ajax.pyj`. No fetch, no promises.
- **Offline.** `resources/content-server/service_worker.js` caches only the page. Downloaded books live in IndexedDB (`read_book/db.pyj`, database `calibre`).
- **Settings.** In localStorage, and synced to the server per user through `/interface-data/set-session-data` (`session.pyj`).
- **Translations.** `_()` strings, sent by the server in the startup data from `content-server/locales.zip`.

## The reader

- **Pre-rendered by the server.** `srv/render_book.py` turns each chapter into a JSON tree, versioned by `RENDER_VERSION`. `read_book/` rebuilds it in a sandboxed iframe, pages it with CSS columns (`paged_mode.pyj`), keeps places with CFIs and searches in a Web Worker.
- **Shared with the desktop viewer.** `viewer-main.pyj` compiles the same `read_book/` into `resources/viewer.js` for `gui2/viewer`. About 50 `runtime.is_standalone_viewer` branches tell the two apart. A change here changes the desktop reader, and zen's reader look (`src/calibre_zen/reader/look/`) is injected into that same code.

## The server

- **calibre's own HTTP server.** A `select()` loop with a pool of 10 threads (`srv/loop.py`, `srv/pool.py`), and worker processes for long jobs (`srv/jobs.py`). WebSockets exist (`web_socket.py`).
- **Routes.** `@endpoint(route, auth_required=True, needs_db_write=False, postprocess=...)` in `srv/routes.py`. `Router.add` refuses a key that already exists. Modules: `code`, `ajax`, `books`, `cdb`, `content`, `convert`, `fts`, `legacy`, `opds`, `users_api`, plus content-server plugins.
- **What the web app calls.**

  | Feature | Endpoints |
  |---|---|
  | Start and book list | `/interface-data/{init,update,books-init,more-books,get-books,newly-added,book-metadata,tag-browser,browse-field,field-names,field-id-map,set-session-data}` |
  | Covers and downloads | `/get/{cover,thumb,<format>}/...`, `/data-files/get/...` |
  | Reader | `/book-manifest`, `/book-file`, `/book-{get,set}-last-read-position`, `/book-{get,update}-annotations`, `/reader-profiles/*`, `/reader-background/*`, `/mathjax/*` |
  | Editing | `/cdb/{set-fields,set-cover,add-book,delete-books,copy-to-library}`, `/data-files/{upload,remove}`, `/set-note` |
  | Notes | `/get-note`, `/get-note-from-item-val`, `/get-note-resource` |
  | Conversion | `/conversion/{book-data,start,status}` |
  | Full-text search | `/fts/{search,snippets,indexing,reindex,disable}` |
  | Account | `/users/change-pw` |
  | Not the web app | `/opds*`, `/ajax/*`, `/mobile`, `/browse`, `/legacy/*`, `/cdb/cmd/*` (calibredb over HTTP) |

- **What zen adds, from outside.** `/zen/status` and `/zen/stop` (`host/endpoints.py`, installed on the host only), and two lock fixes (`host/fixes.py`, host and the window's server).

## Login

- **Off unless `--enable-auth`.** Digest by default, Basic with TLS or `--auth-mode basic` (`srv/auth.py`).
- **The browser's own prompt.** No login page, no sessions, no log out. The only cookie is a one-hour download workaround for Android.
- **Users** are in SQLite, `server-users.sqlite`, with passwords stored in plain text (`srv/users.py`). Each has read-only or not, allowed libraries, a search that limits which books they see per library, and synced settings.
- **Writes** need a signed-in user who is not read-only, or `--local-write` from this computer, or `--trusted-ips`. Without login the server is read-only.
- **Ban** after 5 failed logins when `--ban-for` is set. Users are managed with `--manage-users`.

## Features in the browser

These are the panels `book_list/` registers, which is the list feature parity is measured against.

| Panel | What it does |
|---|---|
| `home` | recently read, recently added, libraries |
| `book_list` | cover grid, details list or custom template, with paging |
| `book_list^search`, `^search^prefs` | search, and the tag browser's settings |
| `book_list^sort`, `^vl`, `^choose_mode` | sort, virtual library, view mode |
| `nav_list` | the sidebar: tag browser, saved virtual libraries |
| `book_list^add` | upload books |
| `book_list^prefs` | per-user settings |
| `book_details` and its `more_actions`, `search_internet`, `copy_to_library`, `data_files`, `upload_data_file` | one book and what you can do with it |
| `edit_metadata` | every field, including custom columns and the comments editor |
| `convert_book` | conversion with its options |
| `fts` | full-text search |
| `show_note`, `edit_note`, `select_item_for_edit_notes` | notes on authors, tags and so on |
| `local_books` | books downloaded for offline reading |
| the reader | read, highlights, bookmarks, search, profiles, position sync |
