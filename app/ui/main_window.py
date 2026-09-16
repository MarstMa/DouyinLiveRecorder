"""主窗口：顶部横幅 + 主播页（三级导航）+ 系统托盘。"""
import threading
import webbrowser

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from ..config import Config
from ..scheduler import Scheduler
from ..updater import check_for_update
from .settings_dialog import SettingsDialog
from .streamer_page import StreamerPage

def make_app_icon() -> QIcon:
    """程序化生成圆形图标。"""
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#38BDF8"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(4, 4, 56, 56)
    p.setPen(QColor("#06283D"))
    f = QFont("Microsoft YaHei")
    f.setBold(True)
    f.setPixelSize(30)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, "录")
    p.end()
    return QIcon(pm)


class MainWindow(QMainWindow):
    update_found = Signal(str, str)

    def __init__(self, config: Config, scheduler: Scheduler):
        super().__init__()
        self.config = config
        self.scheduler = scheduler
        self._really_quit = False

        self.setWindowTitle("抖音直播录制软件")
        self.setWindowIcon(make_app_icon())
        self.resize(980, 700)

        self._build_ui()
        self._setup_tray()
        self.scheduler.notify.connect(self._on_notify)
        self.update_found.connect(self._on_update_found)
        self._start_detection()
        if self.config.data.get("check_update_on_start", True):
            self._start_update_check()

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        # 顶部横幅
        banner = QFrame()
        banner.setObjectName("banner")
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(20, 16, 20, 16)
        banner_layout.setSpacing(12)

        icon_label = QLabel()
        icon_label.setPixmap(make_app_icon().pixmap(44, 44))
        banner_layout.addWidget(icon_label)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("抖音直播录制软件")
        title.setObjectName("bannerTitle")
        subtitle = QLabel("自动检测开播 · 自动录制 · 自动保存")
        subtitle.setObjectName("bannerSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        banner_layout.addLayout(title_box)
        banner_layout.addStretch(1)

        settings_btn = QPushButton("设置")
        settings_btn.setObjectName("secondaryButton")
        settings_btn.clicked.connect(self._open_settings)
        banner_layout.addWidget(settings_btn)

        root.addWidget(banner)

        # 主播页（内部三级导航）
        self.streamer_page = StreamerPage(self.config, self.scheduler)
        root.addWidget(self.streamer_page, 1)

        self.setCentralWidget(central)

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(make_app_icon(), self)
        self.tray.setToolTip("抖音直播录制软件")
        menu = QMenu()
        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self._show_window)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._quit)
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    # ---------- 检测 ----------
    def _start_detection(self):
        self.scheduler.start()

    def _open_settings(self):
        SettingsDialog(self.config, self).exec()

    # ---------- 检查更新 ----------
    def _start_update_check(self):
        threading.Thread(target=self._update_check_worker, daemon=True).start()

    def _update_check_worker(self):
        r = check_for_update()
        if r.get("ok") and r.get("is_new"):
            self.update_found.emit(r["latest"], r["url"])

    def _on_update_found(self, version, url):
        box = QMessageBox(self)
        box.setWindowTitle("发现新版本")
        box.setText(f"发现新版本 v{version}，是否前往下载？")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.button(QMessageBox.Yes).setText("去下载")
        box.button(QMessageBox.No).setText("稍后")
        box.setDefaultButton(QMessageBox.Yes)
        if box.exec() == QMessageBox.Yes:
            webbrowser.open(url)

    # ---------- 托盘 / 关闭 ----------
    def _on_notify(self, title, message):
        if self.tray and self.tray.isVisible():
            self.tray.showMessage(title, message, QSystemTrayIcon.Information, 5000)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_window()

    def _show_window(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _quit(self):
        self._really_quit = True
        self.scheduler.stop()
        self.tray.hide()
        QApplication.instance().quit()

    def closeEvent(self, event):
        if self._really_quit or not self.tray.isVisible():
            event.accept()
            return
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "抖音直播录制软件",
            "程序仍在后台运行，双击托盘图标可重新打开窗口",
            QSystemTrayIcon.Information,
            3000,
        )
