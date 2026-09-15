#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Copy the glyphs a pack maps out of a downloaded icon set and into assets/.

Only mapped glyphs are vendored: the upstream sets run to thousands of files and
a fork carrying all of them to use thirty is a fork nobody wants to clone.

    python vendor.py tabler <path to the set's svg directory>

Run it again after adding entries to a pack's MAP; it copies what is missing and
says what it did. `--check` reports without copying, for a commit hook.
"""

import os
import re
import sys

COMMENT = re.compile(r'^<!--.*?-->\s*', re.S)


def vendor(pack_name: str, source: str, check: bool = False) -> int:
    from calibre_zen.icons.packs import discover

    pack = discover().get(pack_name)
    if pack is None:
        print(f'no such pack: {pack_name}; have {", ".join(sorted(discover()))}', file=sys.stderr)
        return 2
    missing = pack.missing()
    if not missing:
        print(f'{pack_name}: all {len(pack.mapping)} mapped glyphs are vendored')
        return 0
    if check:
        print(f'{pack_name}: {len(missing)} not vendored: {", ".join(missing)}', file=sys.stderr)
        return 1
    os.makedirs(pack.directory, exist_ok=True)
    absent = []
    for icon_name in missing:
        glyph = pack.glyph(icon_name)[0]
        src = os.path.join(source, f'{glyph}.svg')
        try:
            with open(src) as f:
                svg = f.read()
        except OSError:
            absent.append(f'{icon_name} -> {glyph}')
            continue
        # The upstream files carry a tags/category comment header that is of no
        # use once the glyph is chosen, and it is most of the file.
        with open(os.path.join(pack.directory, f'{glyph}.svg'), 'w') as f:
            f.write(COMMENT.sub('', svg).strip() + '\n')
        print(f'  {icon_name:28} {glyph}')
    print(f'{pack_name}: vendored {len(missing) - len(absent)} glyphs into {pack.directory}')
    if absent:
        print(f'{pack_name}: NOT IN SOURCE: {", ".join(absent)}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--check']
    raise SystemExit(vendor(args[0], args[1] if len(args) > 1 else '', '--check' in sys.argv))
