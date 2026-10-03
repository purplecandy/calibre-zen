#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Develop mode only: the reader's JavaScript, compiled when it changed rather
than on every start.

Run from a source tree, calibre rebuilds `resources/viewer.js` from
`src/pyj` each time a reader starts (`web_view.create_profile` calls
`rapydscript.compile_viewer`): about seven seconds of CPU, for a file this
fork never edits. With a spare reader that is seven seconds behind every book
opened, in a second process, while the first is being read.

`compile_viewer` is wrapped to skip the build when its outputs are newer than
everything it reads. A pulled or edited `.pyj` is newer, and is compiled as
before. A packaged build never calls it.
"""

import os

MARK = 'zen_viewer_js'


def newest(paths) -> float:
    ans = 0.0
    for top in paths:
        if os.path.isfile(top):
            ans = max(ans, os.path.getmtime(top))
            continue
        for dirpath, _dirnames, filenames in os.walk(top):
            for name in filenames:
                try:
                    ans = max(ans, os.path.getmtime(os.path.join(dirpath, name)))
                except OSError:
                    pass
    return ans


def up_to_date(base: str) -> bool:
    "Whether viewer.js and viewer.html are newer than every source compile_viewer reads."
    resources = os.path.join(base, 'resources')
    try:
        built = min(os.path.getmtime(os.path.join(resources, n)) for n in ('viewer.js', 'viewer.html'))
    except OSError:
        return False
    sources = (
        os.path.join(base, 'src', 'pyj'),
        os.path.join(base, 'imgsrc', 'srv'),
        os.path.join(resources, 'content-server', 'reset.css'),
        os.path.join(resources, 'content-server', 'base.css'),
    )
    return newest(sources) <= built


def install() -> bool:
    from calibre.constants import is_running_from_develop

    if not is_running_from_develop:
        return False
    from calibre.utils import rapydscript

    orig = rapydscript.compile_viewer
    if getattr(orig, MARK, False):
        return False

    def compile_viewer():
        try:
            if up_to_date(rapydscript.base_dir()):
                return None
        except Exception:
            pass
        return orig()

    setattr(compile_viewer, MARK, True)
    compile_viewer.__wrapped__ = orig
    rapydscript.compile_viewer = compile_viewer
    return True
