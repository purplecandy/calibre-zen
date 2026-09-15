#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Which QPushButton is which, for 02-buttons.qss.

Qt's only native "primary" signal is `:default`, and it turned out not to be
usable: it is a *live* state that follows keyboard focus among every
`autoDefault` button in a dialog (the default for any button that has a
QDialog ancestor), not a fixed marker of intent. Checked empirically, not
assumed: click Cancel and Cancel becomes `:default`, with no traceable Python
call explaining the change -- QDialogButtonBox never calls `setDefault()` on
its Accept-role button either, Qt just gives it initial focus and lets the
same focus-follows-default mechanism take it from there. Styling `:default`
with a solid fill meant the fill visibly jumped to whatever button was last
clicked.

So "primary" here is a static tag instead, set once and never moved by focus:
`_tag_button_box_roles()` reads the *role* a button was actually given
(`QDialogButtonBox.buttonRole()`, which does not change) rather than asking
Qt which one currently owns Enter, and `_tag_explicit_default()` covers the
~30 places calibre calls `setDefault(True)` directly, outside any button box.
`02-buttons.qss` keeps a much subtler rule on live `:default` itself, so a
button that transiently picks it up while focused still hints "Enter does
this" without reading as though it just became the dialog's primary action.

"Destructive" has still less to go on: `DestructiveRole` exists on
`QDialogButtonBox` but calibre never uses it -- checked across the whole of
gui2, zero hits -- so it is wired up here for free (in case that changes) but
the only real signal today is the icon a delete button already carries,
`trash.png` being the one name calibre uses consistently enough to trust;
`minus.png` and friends are used for ordinary list-row removal too often to
mean "destructive" reliably.

The icon's name is known only where `QIcon.ic(name)` is called; by the time a
button receives the finished `QIcon`, the string is gone. So
`_track_icon_names()` remembers a cache key at the name-is-known point, and
`_tag_buttons()` reads it back at the icon-is-known point -- the same
"wrap it from outside" trick as `theme/rewrite.py`, kept in its own module
because it wraps icon and button methods rather than stylesheet or font ones.
"""

DANGER_ICON_NAMES = frozenset({'trash.png'})

_danger_cache_keys: set = set()
_tracking_installed = False
_tagging_installed = False
_button_box_installed = False
_default_installed = False


def is_danger_icon(icon) -> bool:
    try:
        return icon.cacheKey() in _danger_cache_keys
    except Exception:
        return False


def set_variant(widget, variant) -> None:
    """
    Set (or clear, with variant=None) zenVariant and make Qt repaint for it.

    A dynamic property change is not enough on its own: Qt only re-evaluates
    an attribute selector like [zenVariant=...] the next time a widget is
    polished, which already happened once at construction for every button
    tagged after it was shown -- calibre's own Preferences dialog tags its
    Close button from hide_plugin(), well after the button box was built and
    shown. Checked empirically, not assumed: the property was set correctly
    and the button still painted its old look until unpolish()/polish() ran.
    """
    try:
        if widget.property('zenVariant') == variant:
            return
        widget.setProperty('zenVariant', variant)
        style = widget.style()
        if style is not None:
            style.unpolish(widget)
            style.polish(widget)
        widget.update()
    except Exception:
        pass


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
        if is_danger_icon(icon):
            set_variant(self, 'destructive')

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


def _tag_button_box_roles() -> bool:
    """
    Wrap QDialogButtonBox.__init__ and addButton to tag each button by its
    real, unmoving role -- AcceptRole/YesRole as primary, DestructiveRole
    (unused by calibre today, wired up anyway in case that changes) as
    destructive.

    Re-tags every button in the box on each call rather than tracking just
    the newest one: cheap, since a button box rarely holds more than a
    handful, and correct even for the constructor-with-flags shape
    (`QDialogButtonBox(StandardButton.Ok | StandardButton.Cancel)`), where
    every button already exists by the time our wrapped __init__ runs.
    """
    global _button_box_installed
    if _button_box_installed:
        return True
    from qt.core import QDialogButtonBox

    role_variant = {
        QDialogButtonBox.ButtonRole.AcceptRole: 'primary',
        QDialogButtonBox.ButtonRole.YesRole: 'primary',
        QDialogButtonBox.ButtonRole.DestructiveRole: 'destructive',
    }

    def _tag_all(box):
        try:
            buttons = box.buttons()
        except Exception:
            return
        for b in buttons:
            variant = role_variant.get(box.buttonRole(b))
            if variant is not None:
                set_variant(b, variant)

    orig_init = QDialogButtonBox.__init__
    orig_add = QDialogButtonBox.addButton

    def __init__(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        _tag_all(self)

    def addButton(self, *args, **kwargs):  # noqa: N802  (matching the Qt name is the point)
        ret = orig_add(self, *args, **kwargs)
        _tag_all(self)
        return ret

    try:
        QDialogButtonBox.__init__ = __init__
        QDialogButtonBox.addButton = addButton
    except AttributeError, TypeError:
        return False
    _button_box_installed = True
    return True


def _tag_explicit_default() -> bool:
    """
    Wrap QPushButton.setDefault for the ~30 places calibre calls it directly,
    outside any QDialogButtonBox, so those get the same static primary tag
    instead of relying on live :default.
    """
    global _default_installed
    if _default_installed:
        return True
    from qt.core import QPushButton

    orig = QPushButton.setDefault

    def setDefault(self, val):  # noqa: N802  (matching the Qt name is the point)
        ret = orig(self, val)
        try:
            current = self.property('zenVariant')
        except Exception:
            current = None
        if val and current is None:
            set_variant(self, 'primary')
        elif not val and current == 'primary':
            set_variant(self, None)
        return ret

    try:
        QPushButton.setDefault = setDefault
    except AttributeError, TypeError:
        return False
    _default_installed = True
    return True


def install() -> bool:
    "All four: icon names, the buttons that get one, dialog-button-box roles, and explicit setDefault() calls."
    tracked = _track_icon_names()
    tagged = _tag_buttons()
    boxed = _tag_button_box_roles()
    defaulted = _tag_explicit_default()
    return tracked and tagged and boxed and defaulted
