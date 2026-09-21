#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
This fork's tests. Run them with ./zen-test, never directly: the launcher
points calibre-debug at this tree, gives the run a throwaway config directory
and keeps the platform offscreen. See main.py for what it runs and base.py
for the helpers a test builds on.

A test module is `test_<part>.py`. It is found by name, so nothing has to be
registered.
"""
