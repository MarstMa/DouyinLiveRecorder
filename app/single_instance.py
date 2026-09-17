"""单实例控制：确保软件只运行一个，重复启动时唤醒已有窗口。"""
from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = "DouyinLiveRecorder"


class SingleInstance(QObject):
    """判断本进程是否为唯一实例；不是则通知已有实例并让本进程退出。"""

    # 已有实例收到「重复启动」通知时发出，用于把主窗口唤到前台
    activate = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._server = None

    def is_primary(self) -> bool:
        """本进程是否为唯一实例。返回 False 表示已有实例在运行（已通知它）。"""
        server = QLocalServer(self)
        if server.listen(SERVER_NAME):
            self._server = server
            server.newConnection.connect(self._on_new_connection)
            return True
        self._notify_existing()
        return False

    def _notify_existing(self):
        """通知已有实例：把窗口唤到前台。"""
        sock = QLocalSocket()
        sock.connectToServer(SERVER_NAME)
        if sock.waitForConnected(500):
            sock.write(b"activate")
            sock.flush()
            sock.waitForBytesWritten(500)
        sock.disconnectFromServer()

    def _on_new_connection(self):
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            if sock is None:
                continue
            if sock.waitForReadyRead(500):
                if b"activate" in bytes(sock.readAll()):
                    self.activate.emit()
            sock.disconnectFromServer()
            sock.deleteLater()
