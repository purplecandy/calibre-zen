#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The report, shown before it is sent.

Every path that can send something ends here: one dialog with a plain-language
line about what happened, the exact JSON that will leave the machine, and Send
or Cancel. What is on screen is the payload, byte for byte -- the install id is
stamped before the text is rendered, not at send time, so there is nothing the
reader has not seen. Copy puts the same text on the clipboard for people who
want to read it elsewhere or attach it to an issue instead.

For install failures the dialog carries calibre's own "ask again" checkbox,
stored in the same preference calibre uses for its skippable questions, so
unticking it is the one way to make those reports go without asking.
"""

import json

from qt.core import QCheckBox, QDialog, QDialogButtonBox, QFontDatabase, QLabel, QPlainTextEdit, QSize, Qt, QVBoxLayout

AUTO_SKIP_PREF = 'questions_to_auto_skip'


def render(events: list[dict]) -> str:
    "Pretty JSON. One event is an object; several are a list, each sent as its own report."
    payload = events[0] if len(events) == 1 else events
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)


def is_auto_skipped(name: str) -> bool:
    from calibre.gui2 import gprefs

    try:
        return name in set(gprefs.get(AUTO_SKIP_PREF, ()))
    except Exception:
        return False


def set_auto_skipped(name: str, skipped: bool) -> None:
    from calibre.gui2 import gprefs

    try:
        current = set(gprefs.get(AUTO_SKIP_PREF, ()))
    except Exception:
        current = set()
    if skipped:
        current.add(name)
    else:
        current.discard(name)
    gprefs[AUTO_SKIP_PREF] = sorted(current)


class ReportPreview(QDialog):
    """
    `events` are sent as-is when accepted; they are stamped with the install id
    on construction so the text shown is the text sent. `skip_name`, when given,
    adds the "ask again" checkbox and records its state on Send.
    """

    def __init__(self, parent, title: str, intro_html: str, events: list[dict], skip_name: str | None = None):
        super().__init__(parent)
        from calibre_zen.report import consent

        self.events = events
        self.skip_name = skip_name
        self.sent = False
        uid = consent.install_id(create=True)
        for ev in events:
            if uid:
                ev['user'] = {'id': uid}

        self.setObjectName('zenReportPreview')
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)

        intro = QLabel(intro_html, self)
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(intro)

        n = len(events)
        heading = QLabel(
            'This is the report, exactly as it will be sent:' if n == 1 else f'These are the {n} reports, exactly as they will be sent (each on its own):',
            self,
        )
        heading.setObjectName('zenReportHeading')
        layout.addWidget(heading)

        self.text = QPlainTextEdit(self)
        self.text.setObjectName('zenReportPayload')
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.text.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.text.setPlainText(render(events))
        layout.addWidget(self.text, 1)

        self.checkbox = None
        if skip_name:
            self.checkbox = QCheckBox('Ask before sending reports like this', self)
            self.checkbox.setChecked(True)
            self.checkbox.setToolTip('Untick to send future reports of this kind without showing this window.')
            layout.addWidget(self.checkbox)

        self.bb = QDialogButtonBox(self)
        self.copy_button = self.bb.addButton('Copy', QDialogButtonBox.ButtonRole.ActionRole)
        self.copy_button.clicked.connect(self.copy)
        self.send_button = self.bb.addButton('Send', QDialogButtonBox.ButtonRole.AcceptRole)
        self.send_button.setProperty('zenVariant', 'primary')
        self.cancel_button = self.bb.addButton('Cancel', QDialogButtonBox.ButtonRole.RejectRole)
        self.bb.accepted.connect(self.send)
        self.bb.rejected.connect(self.reject)
        layout.addWidget(self.bb)
        self.send_button.setDefault(True)

    def sizeHint(self) -> QSize:
        return QSize(760, 620)

    def copy(self) -> None:
        from qt.core import QApplication

        QApplication.clipboard().setText(self.text.toPlainText())
        self.copy_button.setText('Copied')

    def send(self) -> None:
        from calibre_zen.report import transport

        for ev in self.events:
            transport.send(ev)
        self.sent = True
        if self.skip_name and self.checkbox is not None:
            set_auto_skipped(self.skip_name, not self.checkbox.isChecked())
        self.accept()


def show(parent, title: str, intro_html: str, events: list[dict], skip_name: str | None = None) -> bool:
    "Modal. Returns whether the reports were sent."
    d = ReportPreview(parent, title, intro_html, events, skip_name=skip_name)
    d.exec()
    return d.sent
