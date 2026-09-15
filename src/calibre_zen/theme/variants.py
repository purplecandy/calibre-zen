#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Which QPushButton is which, for 02-buttons.qss.

Qt gives one variant signal for free: `:default`, already set by calibre or
by Qt itself for a dialog's primary action -- no cooperation needed from this
overlay, `02-buttons.qss` just has to do something with it.

It gives none for "destructive": `QDialogButtonBox.ButtonRole.DestructiveRole`
exists, but calibre never uses it -- checked across the whole of gui2, zero
hits. The only real signal left is the icon a delete button already carries,
`trash.png` being the one name calibre uses consistently enough to trust;
`minus.png` and friends are used for ordinary list-row removal too often to
mean "destructive" reliably.

The name is known only where `QIcon.ic(name)` is called; by the time a button
receives the finished `QIcon`, the string is gone. So `_track_icon_names()`
remembers a cache key at the name-is-known point, and `_tag_buttons()` reads
it back at the icon-is-known point -- the same "wrap it from outside" trick as
`theme/rewrite.py`, kept in its own module because it wraps icon and button
methods rather than stylesheet or font ones.
"""

DANGER_ICON_NAMES = frozenset({'trash.png'})

_danger_cache_keys: set = set()
_tracking_installed = False
_tagging_installed = False


def is_danger_icon(icon) -> bool:
    try:
        return icon.cacheKey() in _danger_cache_keys
    except Exception:
        return False


def _track_icon_names() -> bool:
    """
    Wrap IconResourceManager.__call__ to remember which QIcon instances came
    from a name in DANGER_ICON_NAMES.

    Independent of icons/registry.py's own wrap of the same method, and of
    CALIBRE_ZEN_ICONS: this never changes which icon is returned, only records
    a cache key, so a button gets tagged whether or not the icon pack itself
    is on.
    """
    global _tracking_installed
    if _tracking_installed:
        return True
    from calibre.gui2 import IconResourceManager

    orig = IconResourceManager.__call__

    def __call__(self, name, fallback=b''):
        ans = orig(self, name, fallback)
        if name in DANGER_ICON_NAMES and ans is not None:
            try:
                _danger_cache_keys.add(ans.cacheKey())
            except Exception:
                pass
        return ans

    try:
        IconResourceManager.__call__ = __call__
    except AttributeError, TypeError:
        return False
    _tracking_installed = True
    return True


def _tag_buttons() -> bool:
    """
    Wrap QPushButton.__init__ and setIcon so a button given a dangerous icon
    is tagged zenVariant=destructive for 02-buttons.qss.

    Both are wrapped because calibre uses both shapes about equally:
    `QPushButton(icon, text)` sets the icon from the compiled constructor,
    which does not call back into a Python-level setIcon override -- checked
    empirically, not assumed.
    """
    global _tagging_installed
    if _tagging_installed:
        return True
    from qt.core import QIcon, QPushButton

    orig_init = QPushButton.__init__
    orig_set_icon = QPushButton.setIcon

    def _maybe_tag(self, icon):
        try:
            if is_danger_icon(icon):
                self.setProperty('zenVariant', 'destructive')
        except Exception:
            pass

    def __init__(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        for a in args:
            if isinstance(a, QIcon):
                _maybe_tag(self, a)

    def setIcon(self, icon):  # noqa: N802  (matching the Qt name is the point)
        ret = orig_set_icon(self, icon)
        _maybe_tag(self, icon)
        return ret

    try:
        QPushButton.__init__ = __init__
        QPushButton.setIcon = setIcon
    except AttributeError, TypeError:
        return False
    _tagging_installed = True
    return True


def install() -> bool:
    "Both halves: learn which icons are dangerous, then tag the buttons that get one."
    tracked = _track_icon_names()
    tagged = _tag_buttons()
    return tracked and tagged
