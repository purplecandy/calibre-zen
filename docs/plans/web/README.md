# A new web app

A new browser app for calibre-zen's library, built with Astro and Tailwind, served by calibre's own server, and reaching feature parity with calibre's web app. Started 2026-10-11. Nothing is built yet.

What it replaces is described in [current-state.md](current-state.md).

## Decisions so far

- **Astro and Tailwind.** The same stack as the website, so the two share habits and versions (Astro 7, Tailwind v4).
- **Served by calibre's server.** The host, Docker and the window's Connect/share all serve it. No Node at run time.
- **Feature parity** with calibre's web app is the goal. The panels it has to match are listed in [current-state.md](current-state.md#features-in-the-browser).

## Proposed shape

Each point is a proposal until it moves to the decisions above.

### Static build, an app in the browser

calibre's server cannot run Node, so Astro builds a static site and the browser does the rest. Astro gives the build, the layout, Tailwind and the pages. Each page mounts one interactive part that talks to the server's JSON.

- **Pages with query strings**, not a route per book: `/app/`, `/app/book?id=12&library=books`, `/app/edit?id=12`. A static build cannot know the book ids, and a query string keeps every page a real file.
- **React islands, with shadcn/ui.** The desktop's colour schemes are shadcn's presets already (`theme/tokens/schemes.py`), so its components would look like the desktop with no translation. TanStack Query for the server's data, TanStack Virtual for a grid of 10,000 covers. This is the biggest choice still open, see below.
- **TypeScript**, with types written for each endpoint the app calls.

### Where it lives

| What | Where |
|---|---|
| The Astro project | `web/` at the top of the repo, outside `src/` so its source and `node_modules` never ship |
| Its build | `src/calibre_zen/web/dist/`, gitignored, so packaging picks it up with the rest of `src/` |
| Serving it | `src/calibre_zen/web/serve.py`, routes added with `Router.add` as `/zen/status` is |
| Colours | a `@theme` file generated from `theme/tokens/` by a Python script, checked in, with a test that it is current |

### Serving it

- **At `/app/` while it is built**, beside calibre's app at `/`. Both work on the same server and the same login.
- **On every server zen runs.** `/zen/status` is installed only on the host today. This app needs the window's embedded server too, so the install moves to a hook both share.
- **Behind the same login.** The page routes require auth, so the browser asks once and every `fetch` after it carries the login.
- **`url_prefix` works.** Astro bakes its base path in at build time, and the server's prefix is a setting. The build uses a sentinel base, and `serve.py` rewrites it in HTML, CSS and JS as it serves them, cached in memory. Phase 0 proves this.
- **At parity, a setting picks what `/` serves**: the new app or calibre's. calibre's stays one click away, and OPDS and the other clients are untouched.

### What it talks to

- **calibre's endpoints as they are**, listed in [current-state.md](current-state.md#the-server). Nothing in `src/calibre/srv` changes.
- **A `/zen/api/` endpoint only where calibre's are awkward** for a new client, added from outside and documented where it is added.

### The reader

The reader is 19.5k lines, shared with the desktop viewer, and depends on the server's pre-rendered JSON and the books people already keep offline. Rebuilding it is a project of its own.

- **First, open calibre's reader.** A book's Read button goes to calibre's app at `/#library_id=…&book_id=…&fmt=…&mode=read_book`. Same origin, so the books already downloaded for offline reading are still there.
- **Then, give it zen's look.** `reader/look/` already restyles this same code on the desktop. Injecting it into the web reader is likely a small step, and is worth checking early.
- **A new reader comes last**, if ever, and is its own plan.

### Building and shipping

- **Development.** `npm run dev` in `web/`, with Vite proxying the API to `./calibre-zen --host` on port 8080. Hot reload for the app, calibre's real server behind it.
- **CI.** `zen-ci.yml` gains a Node job: `astro check`, unit tests, a build, and Playwright tests against a host on the test library.
- **Packaging.** `zen package` builds `web/` once, before the platform jobs, and hands `dist/` to each. Docker gets it from the Linux package as it does the rest.

## Open questions

- **React, Preact, Solid or Svelte** for the interactive parts. React with shadcn/ui is the proposal, for the match with the desktop's schemes and the size of its ecosystem. Preact is about a tenth of React's size and runs most of the same components.
- **A JavaScript build in packaging.** Today nothing is compiled. A Node step in `zen package` is new, but it is pure JavaScript and runs once for every platform. The alternative is to commit `dist/`, which keeps packaging as it is and puts a build in every diff.
- **Translations.** calibre's web app is translated through `locales.zip`, keyed by its own strings. The new app starts in English. Whether to reuse calibre's catalogs where the strings match, or bring in a translation tool, can wait until parity.
- **A real login page.** Sessions, log out and a sign-in page that is not the browser's prompt. It is server work, done from outside, and it touches security, so it is its own decision.
- **Where it is first seen.** Behind a toggle in Preferences → Sharing, or just at `/app/` with a link from calibre's app.

## Phases

Each phase ends with something a person can use, and a release.

| # | What | Done when |
|---|---|---|
| 0 | **Foundation.** `web/` with Astro, Tailwind, React and the generated colours. `serve.py` on the host and the window's server. `url_prefix` proven. The Node job in CI and `zen package` | a blank page at `/app/` in a packaged build, behind login, under a prefix |
| 1 | **Browse.** Libraries, the cover grid and the list, paging, search, sort, virtual libraries, the tag browser, book details, covers, downloads, light and dark | reading-only use needs no trip to calibre's app |
| 2 | **Read.** The Read button, recently read on home, offline books listed. calibre's reader with zen's look, if the check works | a book opens and reads on a phone |
| 3 | **Edit.** Metadata with custom columns, cover, add books, delete, copy to library, data files, notes | editing needs no trip to calibre's app |
| 4 | **The rest.** Conversion, full-text search, settings synced per user, change password, the offline page and the install-as-app manifest | every panel in the parity list has a match |
| 5 | **Switch.** The setting for what `/` serves, defaulting to the new app | the new app is what people see first |

## Not in scope

- OPDS, `/ajax`, `/mobile`, `/legacy` and `/cdb/cmd`. They serve other clients and stay as they are.
- Any change to `src/pyj` or `src/calibre/srv`. The fork's rule holds: wrap from outside.
