#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The header and footer sheets: the Python half.

The reader's menu opens as two sheets over the page -- a header with the
contents, search, appearance and the rest, a footer with the reading position
and the page and chapter buttons -- the way Apple Books and Readest do it. The
sheets are built in the page by js/30-sheets.js, which drives calibre through
calibre's own entry points (`trigger_shortcut`, `goto_frac`) and asks this
side for what only Python knows: the reading themes, the current one, where
the reader is, and the words, translated -- and, after it moves the reader,
to record the new position (`sync`).

Three things, all from outside:

`web_view.create_profile`
    calibre adds viewer.js to the profile there; the js/ files go beside it,
    in the application world where calibre's code and `window.python_comm`
    live. A script in the page itself could not reach either.

`EbookViewer.__init__`
    Once the window exists: an inbox on the web view's bridge, and the
    position and contents signals connected to a push.

The inbox
    calibre's bridge delivers a page message by looking up its name on the
    bridge object and calling `.emit` on what it finds (utils/webengine.py,
    `Bridge._dispatch_messages`). It has to be a class-level pyqtSignal only
    to be *offered* to the page; a page script that queues a message by name
    reaches any attribute that has an `emit`. So `bridge.zen_message` is an
    object, not a signal, and calibre's list of signals is untouched.

Every push is a `window.zenReader.receive(state)` in the application world.
Nothing waits for an answer: a page that has not loaded the script yet simply
asks again when its menu opens.
"""

import json

from calibre.utils.localization import _

INBOX = 'zen_message'
SCRIPT_NAME = 'zen-reader-look.js'

# The reading themes in the order a person would scan them: the one that
# follows the system first, light to dark after it. calibre's own order is
# alphabetical, which puts Black first.
SCHEME_ORDER = ('system', 'white', 'sepia-light', 'sepia-dark', 'black')


def labels() -> dict:
    "The sheets' own words. calibre's actions bring their own, already translated."
    return {
        'contents': _('Table of Contents'),
        'search': _('Search'),
        'appearance': _('Themes & Settings'),
        'more': _('More'),
        'smaller': _('Smaller text'),
        'larger': _('Larger text'),
        'customize': _('More settings'),
        'previous_chapter': _('Previous chapter'),
        'previous_page': _('Previous page'),
        'next_page': _('Next page'),
        'next_chapter': _('Next chapter'),
        'position': _('Position in the book'),
    }


def schemes(viewer) -> list:
    "Every reading theme: calibre's, then the reader's own, as name and colours."
    from calibre.gui2.viewer.config import get_session_pref

    defaults = dict(getattr(getattr(viewer, 'actions_toolbar', None), 'default_color_schemes', None) or {})
    user = get_session_pref('user_color_schemes', group=None) or {}
    try:
        from calibre.gui2.viewer.web_view import system_colors

        system = system_colors()
    except Exception:
        system = {}
    ans = []

    def add(key, spec, colours=None):
        colours = colours or spec
        ans.append({
            'key': key,
            'name': spec.get('name') or key,
            'bg': colours.get('background') or '#ffffff',
            'fg': colours.get('foreground') or '#000000',
        })

    for key in sorted(defaults, key=lambda k: (SCHEME_ORDER.index(k) if k in SCHEME_ORDER else len(SCHEME_ORDER), k)):
        add(key, defaults[key], system if key == 'system' else None)
    for key in sorted(user, key=lambda k: (user[k].get('name') or k).lower()):
        add(key, user[key])
    return ans


def chapter(viewer) -> str:
    current = getattr(getattr(viewer, 'toc_model', None), 'zen_current', None)
    return getattr(current, 'title', '') or ''


def state(viewer, full: bool = False) -> dict:
    data = getattr(viewer, 'current_book_data', None) or {}
    ans = {'pos_frac': data.get('pos_frac'), 'chapter': chapter(viewer)}
    if full:
        from calibre.gui2.viewer.config import get_session_pref

        ans['current_scheme'] = get_session_pref('current_color_scheme', group=None) or 'system'
        ans['schemes'] = schemes(viewer)
        ans['labels'] = labels()
    return ans


class Inbox:
    "What the page's `zen_message` reaches. See the module docstring for why it is not a signal."

    def __init__(self, viewer):
        self.viewer = viewer

    def emit(self, payload=None, *_args):
        want = payload.get('want') if isinstance(payload, dict) else None
        if want == 'state':
            push(self.viewer, full=True)
        elif want == 'sync':
            sync(self.viewer)

    def connect(self, *_args, **_kwargs):
        # calibre connects every bridge signal it declares; this one it never
        # declared, but be a harmless signal if anything ever tries.
        pass


def push(viewer, full: bool = False) -> None:
    try:
        from qt.webengine import QWebEngineScript

        payload = json.dumps(state(viewer, full))
        viewer.web_view.page().runJavaScript(
            f'window.zenReader && window.zenReader.receive({payload})',
            QWebEngineScript.ScriptWorldId.ApplicationWorld,
        )
    except Exception:
        import traceback

        traceback.print_exc()


def sync(viewer) -> None:
    """
    Record where the reader is after the footer moved it.

    calibre ignores position reports while its menu is open (view.pyj
    `on_update_cfi`, a workaround for Android's on-screen keyboard), and the
    footer turns pages with the menu open. Without this a page turned there
    would be neither shown in the bar nor saved as the last read position. So
    ask the page where it is, and hand the answer to the same two handlers a
    report would have reached.
    """

    def done(data):
        if not isinstance(data, dict):
            return
        cfi, frac = data.get('cfi'), data.get('progress_frac')
        if cfi:
            viewer.web_view.current_cfi = cfi
            viewer.cfi_changed(cfi)
        if frac is not None:
            viewer._on_last_read_pos_data(cfi, frac)
        push(viewer)

    try:
        viewer.web_view.get_current_cfi(done)
    except Exception:
        import traceback

        traceback.print_exc()


def attach(viewer) -> None:
    viewer.web_view.bridge.zen_message = Inbox(viewer)
    wv = viewer.web_view
    wv.update_last_read_position.connect(lambda *_a: push(viewer))
    # After the contents panel's own handler, so the chapter it names is the new one.
    wv.update_current_toc_nodes.connect(lambda *_a: push(viewer))


def wrap_profile(web_view, scripts) -> bool:
    orig = web_view.create_profile
    if getattr(orig, 'zen_reader_look', False):
        return False
    done = []

    def create_profile():
        # calibre caches its profile on the function as `create_profile.ans`,
        # looked up by the module-level name, which is now this function --
        # so the cache lives here, and calibre's code is none the wiser.
        ans = orig()
        if not done:
            done.append(True)
            src = scripts()
            if src:
                from qt.webengine import QWebEngineScript

                from calibre.utils.webengine import create_script

                ans.scripts().insert(
                    create_script(
                        SCRIPT_NAME,
                        src,
                        world=QWebEngineScript.ScriptWorldId.ApplicationWorld,
                        injection_point=QWebEngineScript.InjectionPoint.DocumentReady,
                        on_subframes=False,
                    )
                )
        return ans

    create_profile.zen_reader_look = True
    create_profile.__wrapped__ = orig
    web_view.create_profile = create_profile
    return True


def wrap_window(ui) -> bool:
    cls = ui.EbookViewer
    orig = cls.__init__
    if getattr(orig, 'zen_sheets', False):
        return False

    def __init__(self, *a, **k):
        orig(self, *a, **k)
        try:
            attach(self)
        except Exception:
            import traceback

            traceback.print_exc()

    __init__.zen_sheets = True
    __init__.__wrapped__ = orig
    cls.__init__ = __init__
    return True


def install(web_view, ui, scripts) -> bool:
    return any([wrap_profile(web_view, scripts), wrap_window(ui)])
