#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The menubar app on macOS, the tray app elsewhere: it runs the host in the
background and shows whether the library is shared, and where.

    main.py      the entry point: one tray per person, a plain QApplication
    keeper.py    the host's child process: start, ask, notice, start again
    menu.py      the icon and its menu
    icon.py      the icon: the app icon's waves, cut out of a square
    settings.py  the three settings the menu changes, where the full app keeps them

It is a plain QApplication, not calibre's Application: no calibre look, no
fonts, no hooks. That is the difference between about 40 MB and about 160 MB
for something that sits in the menubar all day.
"""
