#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The Edit metadata dialog, laid out compact.

calibre already chooses its single-book editor from a table of dialog classes,
`calibre.gui2.metadata.single.editors`, keyed by the `edit_metadata_single_layout`
preference -- that is where its own Default, Compact metadata and All on 1 tab
come from. The overlay adds a fourth entry and makes it the default. The class
is a `MetadataSingleDialogBase` like the other three: every widget, every
commit, Previous/Next, Download metadata and its undo are calibre's own code,
and only `do_layout` is ours. See dialog.py.

Two wraps, both from outside:

`single.editors` / `gprefs.defaults['edit_metadata_single_layout']`
    One more key in the table, and the default pointed at it. A reader who
    picked a layout in Preferences keeps it; one who never did gets ours.

`EditMetadataTab.register`
    The Preferences page registers the layout setting with a fixed list of
    choices. The wrap adds ours to that list, so the setting can be moved
    back and forth like any other.

Off with `CALIBRE_ZEN_EDITOR=0`: the key is never added, `edit_metadata()`
falls back to `default` for an unknown layout, and calibre's dialog is back.
"""

from calibre_zen import features

LAYOUT_KEY = 'zen'
LAYOUT_TITLE = 'Compact (calibre-zen)'
PREF_KEY = 'edit_metadata_single_layout'

_installed = False


def enabled() -> bool:
    return features.enabled('editor')


def install() -> bool:
    """
    Register the dialog. Safe to call twice.

    Needs a QApplication: importing calibre's metadata dialog pulls in modules
    that evaluate `QIcon.ic()` at import time.
    """
    global _installed
    if _installed or not enabled():
        return _installed
    from calibre.gui2 import gprefs
    from calibre.gui2.metadata import single
    from calibre.gui2.preferences.look_feel_tabs.edit_metadata import EditMetadataTab
    from calibre_zen.editor.dialog import MetadataSingleDialogZen

    single.editors[LAYOUT_KEY] = MetadataSingleDialogZen
    gprefs.defaults[PREF_KEY] = LAYOUT_KEY

    orig_register = EditMetadataTab.register

    def register(self, name, config_obj, *args, **kwargs):
        if name == PREF_KEY:
            choices = list(kwargs.get('choices') or ())
            if all(value != LAYOUT_KEY for _title, value in choices):
                choices.insert(0, (_(LAYOUT_TITLE), LAYOUT_KEY))
            kwargs['choices'] = choices
        return orig_register(self, name, config_obj, *args, **kwargs)

    EditMetadataTab.register = register
    _installed = True
    return True
