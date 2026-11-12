# The web app

calibre-zen's new browser app, served at `/app/` by calibre's own server.
Astro, Tailwind, React and shadcn/ui. The plan is in
[`docs/plans/web/`](../docs/plans/web/), and how it is served is in
`src/calibre_zen/README.md`, "The web app".

## Working on it

```bash
npm install
./calibre-zen --host        # from the repo root: calibre's server on :8080
npm run dev                 # http://localhost:4321/app/, data proxied to :8080
```

`ZEN_WEB_SERVER=http://127.0.0.1:8099 npm run dev` points the proxy at
another server. The proxied paths are listed in `astro.config.mjs`.

For a library with covers and a few thousand books, serve copies of the demo
libraries with the test server, which takes no lock and runs beside an open
calibre-zen:

```bash
cp -R ../.calibre-zen/gutenberg-library /tmp/Gutenberg
cp -R ../.calibre-zen/perf-library /tmp/Perf
CALIBRE_DEVELOP_FROM=$PWD/../src QT_QPA_PLATFORM=offscreen \
  /Applications/calibre.app/Contents/MacOS/calibre-debug -e e2e/server.py -- \
  8099 --library /tmp/Gutenberg --library /tmp/Perf --local-write
ZEN_WEB_SERVER=http://127.0.0.1:8099 npm run dev
```

`--local-write` lets this computer change the copies without a login, for
converting a book or turning on full-text search. Leave it out to see the app
as someone who may only read.

## Checks

```bash
npm run format              # or format:check, as CI runs it
npm run check               # astro check: types
npm run build               # into ../src/calibre_zen/web/dist
npm run e2e                 # the build in Chrome, against calibre's real server
```

`e2e` starts a server per way the app is served, with `calibre-debug`
(`e2e/server.py`): plain, under `/books`, behind a login, one this computer
can edit (`--local-write`), and the rest server: behind a login, with a TXT
file for every book and its own copy of the build, which the update test
changes. And one with calibre's app at `/` (`CALIBRE_ZEN_WEB_HOME=calibre`).
`CALIBRE_DEBUG` points at another calibre-debug; locally it is the one in
`/Applications/calibre.app`.

## Generated files, checked in

- **`src/styles/tokens.css`**, the desktop's colour schemes as shadcn's
  variables. After a change to `src/calibre_zen/theme/tokens/`:

  ```bash
  CALIBRE_DEVELOP_FROM=$PWD/../src /Applications/calibre.app/Contents/MacOS/calibre-debug \
      -c 'from calibre_zen.web.tokens import main; main()'
  ```

- **`public/*.png` and `favicon.ico`**, the install icons, from
  `public/icon.svg`, which is a copy of `imgsrc/calibre.svg`: `npm run icons`.

## Rules

- **Pages are files.** A static build cannot know book ids, so a page takes
  them in its query string: `/app/book/?id=12`, not `/app/book/12`.
- **Every URL goes through `src/lib/base.ts`.** The server's prefix is only
  known when the file is served.
- **Browser-only code renders with `client:only="react"`.** Astro renders
  islands at build time otherwise, where there is no `window`.
- **The address bar is the state.** Library, search, filters, sort, view and
  the open book live in `src/lib/state.ts`, so back works and every view is
  a link.
- **Offline, nothing changes.** Anything that writes to the server is turned
  off when `useOnline()` from `src/lib/hooks` is false. The copy kept in
  IndexedDB is written by the library page and read only by a page opened
  with no network, so online every page asks the server as it always did.
- **Book lists are virtual.** Only rows on screen exist and only their pages
  of 100 are fetched (`useBookList`), so a big library costs what a small
  one does.
- **calibre's reader database is calibre's.** `src/lib/device.ts` reads the
  `calibre` IndexedDB database the reader keeps, and removes a book from it
  the way the reader does. It never creates it: an empty one would stop the
  reader from setting it up.

## How the code is organised

There is one way to do each of these, and it lives in `src/lib/`. A
component uses it and does not write its own.

- **Talking to the server is `http.ts`.** `request`, `post` and `qs`, with
  `ServerError` for a no. Only uploads use XHR, for their progress.
- **Failures are `errors.ts`.** `describeError(e)` gives the sentence to show
  and what a person can do next. A screen passes its own wording for the
  answers that mean something there. The query client's retry rule is here
  too.
- **State outside React is `store.ts`.** `createStore` gives `get`, `set`,
  `subscribe` and a `use()` hook. It is only for state that lives outside
  React by nature: the address, settings kept in localStorage and on the
  server, and the service worker. Today those are `state.ts`, `prefs.ts`
  and `pwa.ts`.
- **UI state lives in React.** A dialog, a panel or a form is `useState` in
  the component that shows it. When several places open the same thing,
  like Change password from the menu and from Settings, it gets a provider
  that renders it once near the top, and a hook that hands out the callback
  to open it (`useChangePassword()`). No module-level `let` or store for UI
  state.
- **Something opened over the page closes with Back** when the page opened
  it. Use `openStep` and `closeStep` from `state.ts`, which mark the step in
  `history.state`, not a flag of your own.
- **The address is `url.ts`.** It reads and writes this page's parameters and
  builds the links between pages. `state.ts` is the library's address, on
  top of it.
- **localStorage is `storage.ts`.** Every read can fall back and every write
  may not be kept.
- **Showing a value is `format.ts`.** Dates, counts, authors, stars, series
  numbers and page titles. The appearance menu's names are in
  `appearance.ts`.
- **Hooks any page can use are in `hooks/`,** one file each. A component file
  defines no hook of its own unless it is about that one page.
- **remeda is for helpers in `lib/` and models,** not inline in JSX.

So a component never calls `fetch`, `localStorage`, `location.search` or
`document.title` itself, and never builds a link by hand.

Two more sets of rules are on the way. The next change moves every query
into `lib/queries/`, so a component never calls `useQuery`, `useMutation` or
`queryClient` itself. The one after it adds shared dialog and form shells,
and moves the models out of `components/`.
