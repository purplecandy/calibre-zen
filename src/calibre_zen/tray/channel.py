#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The window tells the tray what it is doing, the moment it does it.

Without this the tray only learns about the window from calibre's `GUI` lock,
looked at every two seconds, and after the window quits it waits eight more in
case calibre is restarting. Its menu says "Paused while Calibre Zen is open"
for ten seconds after the window has gone, and "Open Calibre Zen" can be
chosen twice while the first one is still starting. So the window says:

    opened      the window is up: the tray stops saying "Opening…"
    closing     the window is quitting for good: no restart to wait for
    handover    the same, from Restart in headless mode: the tray takes over
                and says once that the library is still shared
    restarting  calibre's restart: a new window opens in a few seconds

The tray answers "ok" to a message it knows. An answer is how Restart in headless mode knows a tray
is already running and does not start a second one.

These are hints. The lock stays the truth: a message that is lost, or a
window that crashes and says nothing, costs the old wait, never a library
opened twice.

A QLocalServer, named per config directory as the tray's own lock is, so a
tray only hears windows that share its settings.
"""

import hashlib

from qt.core import QLocalServer, QLocalSocket, QObject, pyqtSignal

OPENED, CLOSING, HANDOVER, RESTARTING = 'opened', 'closing', 'handover', 'restarting'
MESSAGES = frozenset((OPENED, CLOSING, HANDOVER, RESTARTING))
ACK = 'ok'
TIMEOUT_MS = 500  # the window waits at most this long for a tray; with none it fails at once


def server_name(config_dir: str | None = None) -> str:
    if config_dir is None:
        from calibre.constants import config_dir
    from calibre.constants import __appname__

    digest = hashlib.sha1(config_dir.encode('utf-8', 'surrogatepass')).hexdigest()[:12]
    return f'{__appname__}-tray-{digest}'


def send(message: str, name: str | None = None, timeout_ms: int = TIMEOUT_MS) -> bool:
    """
    Tell the tray, if one is listening. Blocks for at most about
    `timeout_ms`. True when a tray answered.
    """
    s = QLocalSocket()
    s.connectToServer(name or server_name())
    try:
        if not s.waitForConnected(timeout_ms):
            return False
        s.write((message + '\n').encode('ascii'))
        if not s.waitForBytesWritten(timeout_ms):
            return False
        answer = b''
        while b'\n' not in answer and s.waitForReadyRead(timeout_ms):
            answer += bytes(s.readAll())
        return answer.strip().decode('ascii', 'replace') == ACK
    finally:
        s.abort()


class Server(QObject):
    "The tray's end. `received` carries each message it understands."

    received = pyqtSignal(str)

    def __init__(self, name: str | None = None, parent=None):
        super().__init__(parent)
        self.name = name or server_name()
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self._accept)

    def listen(self) -> bool:
        # A tray that crashed leaves its socket file behind on macOS and
        # Linux. The tray's own lock is already held by now, so no other
        # tray is using this name.
        QLocalServer.removeServer(self.name)
        return self.server.listen(self.name)

    def close(self) -> None:
        self.server.close()

    def _accept(self) -> None:
        while self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            sock.setParent(self)
            buf = []

            def ready(sock=sock, buf=buf):
                buf.append(bytes(sock.readAll()))
                data = b''.join(buf)
                if b'\n' not in data:
                    if len(data) > 256:
                        sock.abort()
                    return
                message = data.split(b'\n', 1)[0].strip().decode('ascii', 'replace')
                known = message in MESSAGES
                sock.write(((ACK if known else '?') + '\n').encode('ascii'))
                sock.flush()
                sock.disconnectFromServer()
                if known:
                    self.received.emit(message)

            sock.readyRead.connect(ready)
            sock.disconnected.connect(sock.deleteLater)
            if sock.bytesAvailable():
                ready()
