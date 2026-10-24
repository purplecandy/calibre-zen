# A new web app

A new browser app for calibre-zen's library, built with Astro and Tailwind, served by calibre's own server, and reaching feature parity with calibre's web app. Started 2026-10-11. Phase 0 is built on `wt/web-revamp`, Phase 1 on `wt/web-browse`: `web/README.md` has the commands.

What it replaces is described in [current-state.md](current-state.md).

## Decisions so far

- **Astro and Tailwind.** The same stack as the website, so the two share habits and versions (Astro 7, Tailwind v4).
- **Served by calibre's server.** The host, Docker and the window's Connect/share all serve it. No Node at run time.
- **Feature parity** with calibre's web app is the goal. The panels it has to match are listed in [current-state.md](current-state.md#features-in-the-browser).
- **React islands with shadcn/ui** for everything interactive. Decided 2026-10-11.
- **A Node build step in `zen package`**, not a committed `dist/`. Decided 2026-10-11.
- **At `/app/` for now**, beside calibre's app at `/`. Decided 2026-10-11.
- **A PWA.** It installs to a phone's home screen or a computer's dock, and opens offline. Decided 2026-10-11, see [The PWA](#the-pwa).

## Proposed shape

How the decisions above fit together. A point that is not in them is still a proposal.

### Static build, an app in the browser

calibre's server cannot run Node, so Astro builds a static site and the browser does the rest. Astro gives the build, the layout, Tailwind and the pages. Each page mounts one interactive part that talks to the server's JSON.

- **Pages with query strings**, not a route per book: `/app/`, `/app/book?id=12&library=books`, `/app/edit?id=12`. A static build cannot know the book ids, and a query string keeps every page a real file.
- **React islands, with shadcn/ui.** The desktop's colour schemes are shadcn's presets already (`theme/tokens/schemes.py`), so its components look like the desktop with no translation. TanStack Query for the server's data, TanStack Virtual for a grid of 10,000 covers.
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
- **On every server zen runs.** The host installs the route directly, and the window's server gets it through a wrap of `embedded.Server.__init__`. `/zen/status` stays on the host only: what it reports is the host's.
- **The same login, the same split as calibre's page.** Decided in Phase 0. The app's files are public, as calibre's page is: they hold no books or names. The data needs the login, and the browser asks on the first request. Making the files need the login too would put a 401 in front of the service worker and the manifest, for nothing to protect.
- **`url_prefix` works.** Astro bakes its base path in at build time, and the server's prefix is a setting. The build uses a placeholder base, `/__zen_prefix__/app/`, and `serve.py` replaces it in every text file as it serves it, cached per server. Proven in Phase 0, in Chrome, with `--url-prefix /books`.
- **At parity, a setting picks what `/` serves**: the new app or calibre's. calibre's stays one click away, and OPDS and the other clients are untouched.

### What it talks to

- **calibre's endpoints as they are**, listed in [current-state.md](current-state.md#the-server). Nothing in `src/calibre/srv` changes.
- **A `/zen/api/` endpoint only where calibre's are awkward** for a new client, added from outside and documented where it is added.

### The reader

The reader is 19.5k lines, shared with the desktop viewer, and depends on the server's pre-rendered JSON and the books people already keep offline. Rebuilding it is a project of its own.

- **First, open calibre's reader.** A book's Read button goes to calibre's app at `/#library_id=…&book_id=…&fmt=…&mode=read_book`. Same origin, so the books already downloaded for offline reading are still there.
- **Then, give it zen's look.** `reader/look/` already restyles this same code on the desktop. Injecting it into the web reader is likely a small step, and is worth checking early.
- **A new reader comes last**, if ever, and is its own plan.

### The PWA

- **A manifest and a service worker of our own**, at `/app/manifest.webmanifest` and `/app/sw.js` with scope `/app/`. Workbox's `generateSW`, run after Astro's build (`web/integrations/pwa.mjs`): `@vite-pwa/astro` does not support Astro 7. Every URL it precaches is relative to `sw.js`, so the worker needs no prefix. calibre's own worker sits at `/` and only touches the page at `/` itself, so the two never answer for the same URL.
- **The app opens offline.** The whole build is precached, so the shell starts with no network.
- **The library opens offline.** TanStack Query's cache is kept in IndexedDB, and covers in a runtime cache. Offline, the last book list and details are shown, marked as offline, and editing is turned off.
- **Books read offline**, through calibre's reader and its own IndexedDB, at the same origin. Its page at `/` is cached by calibre's worker. A new reader would bring offline reading into `/app/` itself.
- **Updates** prompt rather than reload under someone mid-task: "A new version is ready", with a button.
- **Icons** for every platform, from the app's own icon, generated in the build.

What a PWA needs that the plan has to answer:

- **HTTPS.** Browsers allow a service worker and an install only on HTTPS or `localhost`. A home server at `http://192.168.1.20:8080` gets the web app but no install and no offline. The ways to HTTPS are calibre's own `--ssl-certfile`, a reverse proxy, or `tailscale serve`. The beginner's guide and the Docker README gain a section on it, and the app says plainly why it cannot be installed when it is on plain HTTP.
- **The login.** Settled by design in Phase 0. The worker caches only the public files and lets every data request through untouched, so the browser's prompt works as it does without a worker. Chrome is tested in CI. Safari and Firefox are still to be tried by hand.
- **`url_prefix`.** The manifest's `scope` and `start_url` and the worker's precache list all carry the base path, so the serve-time rewrite covers them too.
- **iOS.** Safari installs from Share → Add to Home Screen only, keeps a separate storage for the installed app, and may clear it after weeks unused. Offline books may need downloading again there.

### Building and shipping

- **Development.** `npm run dev` in `web/`, with Vite proxying the API to `./calibre-zen --host` on port 8080. Hot reload for the app, calibre's real server behind it.
- **CI.** `zen-ci.yml` gains a Node job: `astro check`, unit tests, a build, and Playwright tests against a host on the test library.
- **Packaging.** `zen package` builds `web/` once, before the platform jobs, and hands `dist/` to each. Docker gets it from the Linux package as it does the rest.

## Open questions

- **Translations.** calibre's web app is translated through `locales.zip`, keyed by its own strings. The new app starts in English. Whether to reuse calibre's catalogs where the strings match, or bring in a translation tool, can wait until parity.
- **A real login page.** Sessions, log out and a sign-in page that is not the browser's prompt. It is server work, done from outside, and it touches security, so it is its own decision.
- **A link to it.** Whether calibre's app at `/` links to `/app/` before the switch, and how, without editing `src/pyj`.

## Phases

Each phase ends with something a person can use, and a release.

| # | What | Done when |
|---|---|---|
| 0 | **Foundation.** `web/` with Astro, Tailwind, React, shadcn/ui and the generated colours. `serve.py` on the host and the window's server. `url_prefix` proven. The manifest and service worker, with the login check above. The Node job in CI and `zen package` | a blank page at `/app/` in a packaged build, behind login, under a prefix, installable over HTTPS. **Built 2026-10-12**. Packaged for Linux in CI, and for macOS by hand on 2026-10-24, under a prefix. Windows untried |
| 1 | **Browse.** Libraries, the cover grid and the list, paging, search, sort, virtual libraries, the tag browser, book details, covers, downloads, light and dark. The app shell opens offline | reading-only use needs no trip to calibre's app. **Built 2026-10-12** on `wt/web-browse` |
| 2 | **Read.** The Read button, recently read on home, offline books listed. calibre's reader with zen's look, if the check works | a book opens and reads on a phone |
| 3 | **Edit.** Metadata with custom columns, cover, add books, delete, copy to library, data files, notes | editing needs no trip to calibre's app |
| 4 | **The rest.** Conversion, full-text search, settings synced per user, change password. The library browsable offline, and the update prompt | every panel in the parity list has a match |
| 5 | **Switch.** The setting for what `/` serves, defaulting to the new app | the new app is what people see first |

## Not in scope

- OPDS, `/ajax`, `/mobile`, `/legacy` and `/cdb/cmd`. They serve other clients and stay as they are.
- Any change to `src/pyj` or `src/calibre/srv`. The fork's rule holds: wrap from outside.
