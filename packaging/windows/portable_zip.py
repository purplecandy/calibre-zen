#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>
"""
Zip the staged Calibre Zen Portable folder for the portable installer.

Deflate, written by Python's zipfile exactly as upstream's bypy does (there
stored, then lzip-compressed; here deflate, since the installer has no
lzma). zipfile seeks back to write each entry's sizes into its local header,
so the archive has no data descriptors and no zip64 records, which is what
the installer's XUnzip can read. Empty directories are entered explicitly:
Calibre Library\\ and Calibre Settings\\ must exist after extraction.

    calibre-debug -e portable_zip.py -- <folder> <out.zip>
"""

import os
import sys
import zipfile


def main():
    args = [a for a in sys.argv[1:] if a != '--']
    if len(args) != 2:
        raise SystemExit(__doc__)
    folder, out = os.path.abspath(args[0]), os.path.abspath(args[1])
    root = os.path.basename(folder)
    n = 0
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for dirpath, dirnames, filenames in os.walk(folder):
            dirnames.sort()
            rel = os.path.relpath(dirpath, folder)
            arc = root if rel == '.' else f'{root}/{rel.replace(os.sep, "/")}'
            zf.mkdir(arc)
            for name in sorted(filenames):
                zf.write(os.path.join(dirpath, name), f'{arc}/{name}')
                n += 1
    print(f'    {n} files, {os.path.getsize(out) / 1e6:,.0f} MB -> {out}')


if __name__ == '__main__':
    main()
