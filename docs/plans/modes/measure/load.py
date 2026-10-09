#!/usr/bin/env python3
"""
Many readers on one calibre-server at once, the way the web app and a Mini
window would use it: searches, pages of books, single books, cover
thumbnails, the tag browser, and a few small writes.

Standard library only, so it runs under any Python 3.10+:

    python3 load.py --base http://127.0.0.1:18099 --library perf-50k --books 50000 --clients 16

Prints one line per kind of request: how many, how many per second, and the
50th, 95th and worst latency in milliseconds. Writes need the server started
with --enable-local-write.
"""

import argparse
import json
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

# Words the seed library is built from, so searches match real books.
AUTHORS = 'Chen Novak Sato Rossi Gupta Okafor Moreau Petrov Kaur Thorne Vance Mercer'.split()
TAGS = ['Fiction', 'Fantasy', 'Science Fiction', 'Cozy', 'Cyberpunk', 'favourite', 'book club', 'to reread']
WORDS = 'Silent Hollow Crimson Broken Hidden Iron Winter Golden Quiet Midnight Velvet Bitter'.split()


def query(r: random.Random) -> str:
    return r.choice((
        lambda: f'authors:"{r.choice(AUTHORS)}"',
        lambda: f'tags:"={r.choice(TAGS)}"',
        lambda: f'title:"{r.choice(WORDS)}"',
        lambda: f'{r.choice(WORDS)} and rating:>={r.randint(1, 5)}',
        lambda: '#read_status:Unread',
        lambda: '',
    ))()


def actions(base: str, lib: str, books: int, write_ratio: float):
    q = urllib.parse.quote

    def search(r):
        return 'search', f'{base}/ajax/search/{lib}?num=50&sort=title&query={q(query(r))}', None

    def page(r):
        return 'page of books', f'{base}/interface-data/get-books?library_id={lib}&num=50&sort=timestamp.desc&search={q(query(r))}', None

    def book(r):
        return 'one book', f'{base}/interface-data/book-metadata/{r.randint(1, books)}?library_id={lib}', None

    def thumb(r):
        return 'thumbnail', f'{base}/get/thumb/{r.randint(1, books)}/{lib}?sz=300x400', None

    def tags(r):
        return 'tag browser', f'{base}/interface-data/tag-browser?library_id={lib}', None

    def write(r):
        body = json.dumps({'changes': {'rating': r.randint(0, 10)}}).encode()
        return 'write rating', f'{base}/cdb/set-fields/{r.randint(1, books)}/{lib}', body

    reads = [(search, 30), (page, 15), (book, 25), (thumb, 25), (tags, 5)]
    total = sum(w for _, w in reads)
    table = [(f, w / total * (1 - write_ratio)) for f, w in reads] + [(write, write_ratio)]
    fns, weights = zip(*table)

    def pick(r):
        return r.choices(fns, weights)[0](r)

    return pick


def client(n: int, pick, until: float, results: dict, lock: threading.Lock, seed: int):
    r = random.Random(seed * 1000 + n)
    local: dict[str, list] = {}
    while time.monotonic() < until:
        name, url, body = pick(r)
        req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'} if body else {})
        t0 = time.perf_counter()
        err = None
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                resp.read()
        except urllib.error.HTTPError as e:
            err = str(e.code)
        except (urllib.error.URLError, OSError) as e:
            err = type(e).__name__
        dt = (time.perf_counter() - t0) * 1000
        slot = local.setdefault(name, [[], {}])
        if err is None:
            slot[0].append(dt)
        else:
            slot[1][err] = slot[1].get(err, 0) + 1
    with lock:
        for name, (times, errors) in local.items():
            slot = results.setdefault(name, [[], {}])
            slot[0].extend(times)
            for k, v in errors.items():
                slot[1][k] = slot[1].get(k, 0) + v


def pct(xs: list, p: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p / 100 * len(xs)))]


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument('--base', default='http://127.0.0.1:18099')
    ap.add_argument('--library', required=True, help='the library id, which is its folder name')
    ap.add_argument('--books', type=int, required=True, help='book ids are 1..books')
    ap.add_argument('--clients', type=int, default=8)
    ap.add_argument('--seconds', type=float, default=20)
    ap.add_argument('--write-ratio', type=float, default=0.05)
    ap.add_argument('--seed', type=int, default=1)
    a = ap.parse_args()

    pick = actions(a.base.rstrip('/'), a.library, a.books, a.write_ratio)
    results: dict[str, list] = {}
    lock = threading.Lock()
    until = time.monotonic() + a.seconds
    threads = [threading.Thread(target=client, args=(i, pick, until, results, lock, a.seed)) for i in range(a.clients)]
    t0 = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.monotonic() - t0

    every = [x for times, _ in results.values() for x in times]
    errors = sum(sum(e.values()) for _, e in results.values())
    rate = len(every) / elapsed
    print(f'   {a.clients} clients, {elapsed:.0f} s: {rate:.0f} requests/s, {errors} errors, p50 {pct(every, 50):.0f} ms, p95 {pct(every, 95):.0f} ms')
    for name in sorted(results, key=lambda k: -len(results[k][0])):
        times, errs = results[name]
        line = f'     {name:<13} {len(times):>6}  {len(times) / elapsed:>6.1f}/s'
        line += f'  p50 {pct(times, 50):>7.0f}  p95 {pct(times, 95):>7.0f}  max {max(times, default=0):>7.0f} ms'
        if errs:
            line += '  errors ' + ', '.join(f'{k}: {v}' for k, v in sorted(errs.items()))
        print(line)


if __name__ == '__main__':
    main()
