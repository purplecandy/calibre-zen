#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

# calibre-debug -e src/calibre_zen/tray/__main__.py -- [--library PATH] [host options]

import sys

from calibre_zen.tray.main import main

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
