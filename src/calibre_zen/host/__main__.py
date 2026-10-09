#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Run the host in the foreground:

    calibre-debug -e src/calibre_zen/host/__main__.py -- [options] [LIBRARY ...]

All the work is in main.py.
"""

from calibre_zen.host.main import main

raise SystemExit(main())
