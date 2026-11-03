import json
import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from .constants import APP_ID

SERVER_NAME = f"{APP_ID}-{getattr(os, 'getuid', lambda: 0)()}"


def send_command(cmd, timeout_ms=500):
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if not sock.waitForConnected(timeout_ms):
        return False
    sock.write((json.dumps(cmd) + "\n").encode("utf-8"))
    sock.flush()
    sock.waitForBytesWritten(1000)
    sock.disconnectFromServer()
    return True


class CommandServer(QObject):
    received = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.server = QLocalServer(self)
        QLocalServer.removeServer(SERVER_NAME)
        self.server.listen(SERVER_NAME)
        self.server.newConnection.connect(self._on_connection)

    def close(self):
        self.server.close()

    def _on_connection(self):
        while self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            buf = bytearray()
            sock.readyRead.connect(lambda sock=sock, buf=buf: self._read(sock, buf))
            sock.disconnected.connect(sock.deleteLater)

    def _read(self, sock, buf):
        buf.extend(bytes(sock.readAll()))
        while b"\n" in buf:
            line, _, rest = bytes(buf).partition(b"\n")
            buf[:] = rest
            try:
                cmd = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                continue
            if isinstance(cmd, dict):
                self.received.emit(cmd)
