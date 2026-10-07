# Two calibre-server bugs to send upstream

Found in phase 0 on 2026-10-08, in calibre 9.15 and in upstream `master` at `ff944d981b`. calibre-zen works around both in its own process for now (`src/calibre_zen/host/fixes.py`). This note is what a pull request to calibre would need.

## Reproducing them

Both need only a running server and a few clients. From this repo, on a copy of any library:

```sh
MEASURE_WRITES=0 docs/plans/modes/measure/measure-load.sh 4 16     # bug 1: HTTP 500s
docs/plans/modes/measure/measure-load.sh 32                         # bug 2: the server hangs
```

`measure-load.sh` starts a stock `calibre-server` on a throwaway copy of the perf library and drives it with [`measure/load.py`](measure/load.py). Bug 2 shows within 15 s at 32 clients with 5% writes, and sometimes at 16.

## 1. Notes are read on the shared connection under the read lock

**What a user sees.** With a few readers at once, some requests for a page of books or one book fail with HTTP 500. The server log shows:

```
apsw.ThreadingViolationError: Cursor couldn't run because the Connection is busy in another thread
```

**Where.**

```
srv/code.py:619          get_books → book_as_json
srv/metadata.py:101      book_as_json → db.items_with_notes_in_book
db/cache.py:789          items_with_notes_in_book   (a @read_api)
db/backend.py:1110       notes_for
db/notes/connect.py:320  get_note → conn.get(...)
db/backend.py:445        Connection.get
```

**Why.** `@read_api` methods hold the shared lock, so many threads can be inside them at once. Most read only the in-memory tables. The notes methods go to SQLite on the one apsw connection, which allows one active cursor at a time across threads.

**Possible fixes.**
- Serialize every backend read that a `@read_api` method makes, with a mutex on the connection.
- Or make the notes read methods take the exclusive lock, as `@write_api` does. This is simpler, but it blocks all readers for each notes lookup.
- The same applies to any other `@read_api` method that queries the backend. That list needs auditing: notes, annotations and FTS are the likely ones.

**The patch** is [`upstream/0001-serialize-sql-reads-on-the-shared-connection.patch`](upstream/0001-serialize-sql-reads-on-the-shared-connection.patch). It takes the first fix, for the 28 methods the audit found.

## 2. Tag browser against a page of books deadlocks once a writer waits

**What a user sees.** Under mixed reads and writes the server stops answering for good. CPU drops to 0%, and SIGTERM is ignored.

**The cycle**, from a `faulthandler` dump of every thread:

| Thread | Holds | Waits for |
|---|---|---|
| The event loop, rendering the tag browser lazily: `srv/code.py:682` → `srv/metadata.py:748` → `srv/handler.py:153` | `Context.lock` | the library's read lock (`db/cache.py:1876`) |
| A worker writing: `srv/cdb.py:250` | nothing | the library's write lock |
| A worker serving a page of books: `srv/code.py:611` holds `db.safe_read_lock`, then `srv/ajax.py:548` → `srv/handler.py:180` | the library's read lock | `Context.lock` |

- `SHLock` makes new readers queue behind a waiting writer (`db/locking.py:167`), so the event loop cannot get its read lock.
- The writer waits for the page-of-books worker to release the read lock, and that worker waits for `Context.lock`, which the event loop holds.
- `etagged_dynamic_response` runs the tag browser's `generate()` on the event-loop thread (`srv/http_response.py:747`). Once that thread blocks, no request is served and no signal is handled.

**Why.** `Context.search` and `Context.get_tag_browser` take `Context.lock` and then call into the library, which takes the read lock. `get_books` and `ajax/search` take the read lock first and then call `Context.search`. Two orders for the same pair of locks.

**Possible fixes.**
- Hold `Context.lock` only around the cache dictionaries, never while calling into the library. Compute the search or the categories outside it, then store the result. This removes the second lock from the cycle. It is the fix closest to how the code reads today.
- Or take the library's read lock first in both `Context` methods. The read lock is reentrant for a thread that already holds it, even with a writer queued (`db/locking.py:158`). This gives one order everywhere.
- Separately, the tag browser's `generate()` should not run on the event-loop thread. Any wait there stalls the whole server.

**The patch** is [`upstream/0002-take-the-read-lock-before-context-lock.patch`](upstream/0002-take-the-read-lock-before-context-lock.patch). It takes the second fix.

## What zen does meanwhile

`calibre_zen/host/fixes.py` patches these methods from outside in every process that serves: zen's own host and the GUI's embedded server. The tests in `src/calibre_zen/tests/test_srvfix.py` reproduce both bugs against unpatched calibre and pass with the patch. The upstream pull request can start from those tests and the two patches in [`upstream/`](upstream/).
