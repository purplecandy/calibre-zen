#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The host: one background process that owns the library and serves it.

It is calibre's own content server, built the way calibre-server builds it,
with four things added from outside:

    options.py     calibre-server's options, with the GUI's Sharing settings
                   as the defaults, plus --auto-add and --no-auto-add
    endpoints.py   GET /zen/status and POST /zen/stop, added to the server's
                   router after calibre has loaded its own routes
    autoadd.py     a watched folder, without the main window
    launch.py      how another zen process starts, asks and stops a host

main.py puts them together. Nothing in src/calibre changes: the server is
calibre.srv.standalone.Server, and the routes go in through Router.add.

See docs/plans/modes/first-cut.md for the contract the tray and the Docker
image build against.
"""
