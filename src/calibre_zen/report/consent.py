#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Nothing leaves without being shown and asked.

calibre's users chose an application that phones nobody, and Zen keeps that.
Every path that can send a report ends in the same window (`preview.py`): what
happened in a sentence, the exact JSON that will be sent, and Send or Cancel.
A crash in our code puts one extra button on the dialog calibre already shows,
which opens that window. A component that failed to install opens it once the
main window is up, with an "ask again" checkbox; unticking it is the only way
to make those reports go without the window. There is no heartbeat and no
usage ping.

The install id is a random UUID minted the first time a report is previewed,
so Sentry can say "3 users" instead of "7 events" without knowing who. It is
stored beside calibre's other GUI preferences and deleting it is harmless.

    CALIBRE_ZEN_REPORT=0    no button, no question, nothing built
"""

import uuid

INSTALL_ID_KEY = 'zen_report_install_id'
AUTO_SEND_QUESTION = 'zen_report_install_failures'
BUTTON_TEXT = 'Report to Calibre Zen…'
SENT_TEXT = 'Report sent'

PRIVACY_LINE = (
    '<p>It contains the error, the lines of code around it, and version numbers. '
    'No book data, file paths or personal details -- read it below before deciding.</p>'
)


def _prefs():
    from calibre.gui2 import gprefs

    return gprefs


def install_id(*, create: bool = True) -> str:
    try:
        prefs = _prefs()
    except Exception:
        return ''
    ans = prefs.get(INSTALL_ID_KEY)
    if not ans and create:
        ans = uuid.uuid4().hex
        prefs[INSTALL_ID_KEY] = ans
    return ans or ''


def auto_send_install_failures() -> bool:
    "True once the user has unticked 'ask again' on the install-failure preview."
    from calibre_zen.report import preview

    return preview.is_auto_skipped(AUTO_SEND_QUESTION)


def send_now(event: dict) -> None:
    "Send without the window. Only for reports the user has already said may go unasked."
    from calibre_zen.report import transport

    uid = install_id(create=True)
    if uid:
        event['user'] = {'id': uid}
    transport.send(event)


def add_send_button(dialog, event: dict):
    """
    The one button on calibre's error dialog. It opens the preview; only Send
    in there sends, and the button becomes a receipt when it does.
    """
    from qt.core import QDialogButtonBox

    btn = dialog.bb.addButton(BUTTON_TEXT, QDialogButtonBox.ButtonRole.ActionRole)
    btn.setToolTip('Shows the report that would be sent to the Calibre Zen maintainers, and lets you send it.')

    def clicked():
        if preview_crash(dialog, event):
            btn.setEnabled(False)
            btn.setText(SENT_TEXT)

    btn.clicked.connect(clicked)
    return btn


def preview_crash(parent, event: dict) -> bool:
    from calibre_zen.report import preview

    msg = "<p>This error happened in Calibre Zen's own code, not in calibre's. Sending the report helps the maintainers fix it.</p>" + PRIVACY_LINE
    return preview.show(parent, 'Report to Calibre Zen', msg, [event])


def ask_install_failure(parent, events: list[dict]) -> bool:
    "A Zen component did not install. Show the report(s); the checkbox is the 'always' switch."
    from calibre_zen.report import preview

    names = sorted({e.get('tags', {}).get('zen.module', '?') for e in events})
    msg = (
        '<p>Part of Calibre Zen could not start and has been switched off for this session: <b>{}</b>. '
        'Everything else, including calibre itself, is unaffected.</p>'
        '<p>This usually means a calibre update changed something Zen relies on. '
        'The report tells the maintainers exactly which part, so it can be fixed for the next release.</p>'
    ).format(', '.join(names)) + PRIVACY_LINE
    return preview.show(parent, 'Calibre Zen: a component did not start', msg, events, skip_name=AUTO_SEND_QUESTION)


def ask_background(parent, ev: dict) -> bool:
    "Our code failed on a worker thread; there was no dialog to put the button on."
    from calibre_zen.report import preview

    msg = (
        '<p>Something in Calibre Zen failed in the background. calibre carried on, and nothing you were doing was affected.</p>'
        '<p>Sending the report helps the maintainers fix it.</p>'
    ) + PRIVACY_LINE
    return preview.show(parent, 'Calibre Zen: a background error', msg, [ev])
