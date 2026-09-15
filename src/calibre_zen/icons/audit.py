#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
What is left to map, and what it could map to.

    calibre-debug -e audit.py -- tabler [<path to the set's svg dir>] [--all]

Lists every icon calibre ships, says which the pack covers, and for the rest
proposes glyphs from the icon set by matching calibre's name against the set's
own names and keyword tags. The proposals are a shortlist to choose from, not a
mapping: string similarity cheerfully offers `dog` for `donate`. Judgement is
the part that is not automatable; finding the candidates is not.

Only the top-level icons are considered. devices/, mimetypes/ and plugins/ are
brand and file-format marks -- a Kindle is not a line drawing of a Kindle -- and
are left to calibre.
"""

import os
import re
import sys

TAGS = re.compile(r'tags:\s*\[(.*?)\]', re.S)
WORD = re.compile(r'[a-z0-9]+')


# Files under images/ that are not UI icons and never will be: the application's
# own marks, the placeholder cover, two webmail logos, and the deliberately
# empty one. Counting them as "unmapped" only makes the number useless.
NOT_ICONS = frozenset({
    'apple-touch-icon.png',
    'blank.png',
    'calibre.svg',
    'default_cover.png',
    'favicon-192.png',
    'favicon-512.png',
    'gmail_logo.png',
    'hotmail.png',
})

THEME_VARIANT = re.compile(r'-for-(dark|light)-theme(?=\.)')


def calibre_icon_names() -> list:
    """
    Every icon name calibre can ask for.

    The -for-dark-theme / -for-light-theme files are dropped: calibre picks
    between them itself and code asks for the base name, which is what reaches
    the pack.
    """
    from calibre.utils.resources import get_path as P

    d = P('images', allow_user_override=False)
    names = set()
    for x in os.listdir(d):
        if not x.endswith(('.png', '.svg')) or x in NOT_ICONS:
            continue
        names.add(THEME_VARIANT.sub('', x))
    return sorted(names)


def tokens(name: str) -> set:
    return set(WORD.findall(os.path.splitext(name)[0].lower().replace('_', ' ').replace('-', ' ')))


def index(source: str) -> dict:
    "glyph stem -> the words that describe it, from its name and its tags."
    ans = {}
    for fname in os.listdir(source):
        if not fname.endswith('.svg'):
            continue
        stem = fname[:-4]
        words = tokens(stem)
        try:
            with open(os.path.join(source, fname)) as f:
                head = f.read(600)
        except OSError:
            head = ''
        m = TAGS.search(head)
        if m:
            words |= set(WORD.findall(m.group(1).lower()))
        ans[stem] = words
    return ans


def suggest(name: str, idx: dict, n: int = 5) -> list:
    want = tokens(name)
    if not want:
        return []
    scored = []
    for stem, words in idx.items():
        hits = want & words
        if not hits:
            continue
        # Whole-name matches first, then how much of calibre's name is covered,
        # then prefer the shorter glyph name: `book` over `book-upload` for
        # `book`.
        score = (10 if stem in want else 0) + len(hits) / len(want) * 5 - len(stem) / 50
        scored.append((score, stem))
    scored.sort(reverse=True)
    return [s for _, s in scored[:n]]


def main(argv) -> int:
    from calibre_zen.icons.packs import discover

    pack_name = argv[0] if argv else 'tabler'
    source = next((a for a in argv[1:] if not a.startswith('--')), '')
    show_all = '--all' in argv

    pack = discover().get(pack_name)
    if pack is None:
        print(f'no such pack: {pack_name}', file=sys.stderr)
        return 2

    names = calibre_icon_names()
    mapped = [n for n in names if n in pack.mapping]
    unmapped = [n for n in names if n not in pack.mapping]
    subdir = sorted(n for n in pack.mapping if '/' in n)
    print(f"{pack_name}: {len(mapped)}/{len(names)} of calibre's top-level icons mapped, {len(unmapped)} to go")
    if subdir:
        print(f'also mapped, out of the brand-mark folders: {", ".join(subdir)}')
    extra = sorted(set(pack.mapping) - set(names) - set(subdir))
    if extra:
        print(f'mapped but not shipped by calibre (harmless, probably renamed upstream): {", ".join(extra)}')
    idx = index(source) if source and os.path.isdir(source) else {}
    if not idx and source:
        print(f'no glyphs found in {source}; listing without proposals', file=sys.stderr)
    print()
    for name in names if show_all else unmapped:
        mark = '=' if name in pack.mapping else ' '
        current = pack.mapping.get(name, '')
        current = current[0] if isinstance(current, tuple) else current
        props = suggest(name, idx) if idx else []
        print(f'{mark} {name:34} {current or "-":20} {" ".join(props)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
