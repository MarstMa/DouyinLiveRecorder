"""全局设置对话框。"""
import threading
import webbrowser

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from .. import autostart
from ..config import APP_VERSION, QUALITY_OPTIONS
from ..updater import check_for_update


class SettingsDialog(QDialog):
    update_checked = Signal(object)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("设置")
        self.setMinimumWidth(420)

        form = QFormLayout()
        form.setSpacing(12)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 600)
        self.interval_spin.setSuffix(" 秒")
        self.interval_spin.setValue(int(config.data.get("detect_interval_seconds", 20)))
        form.addRow("检测间隔：", self.interval_spin)

        self.hot_interval_spin = QSpinBox()
        self.hot_interval_spin.setRange(5, 600)
        self.hot_interval_spin.setSuffix(" 秒")
        self.hot_interval_spin.setValue(int(config.data.get("hot_interval_seconds", 10)))
        form.addRow("热门时段扫描间隔：", self.hot_interval_spin)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(list(QUALITY_OPTIONS.keys()))
        self.quality_combo.setCurrentText(config.data.get("default_quality", "原画"))
        form.addRow("默认画质：", self.quality_combo)

        self.autostart_check = QCheckBox("开机自动启动本软件")
        self.autostart_check.setChecked(autostart.is_enabled())
        form.addRow("", self.autostart_check)

        self.update_check = QCheckBox("启动时自动检查更新")
        self.update_check.setChecked(bool(config.data.get("check_update_on_start", True)))
        form.addRow("", self.update_check)

        cookie_label = QLabel("Cookie（可选，一般无需填写）")
        cookie_label.setStyleSheet("color: #94A3B8;")
        form.addRow(cookie_label)
        self.cookie_edit = QPlainTextEdit()
        self.cookie_edit.setPlaceholderText("如果检测该主播需要登录，可在此粘贴浏览器里的 Cookie")
        self.cookie_edit.setFixedHeight(70)
        self.cookie_edit.setPlainText(config.data.get("cookie", ""))
        form.addRow("Cookie：", self.cookie_edit)

        hint = QLabel("说明：检测间隔越短越及时，但也越容易被抖音限制，建议保持 20 秒。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #94A3B8;")

        # 关于 + 检查更新
        about_row = QHBoxLayout()
        about = QLabel(f"版本：{APP_VERSION} · 作者：MarstMa")
        about.setStyleSheet("color: #94A3B8; font-size: 12px;")
        about_row.addWidget(about)
        about_row.addStretch(1)
        self.update_btn = QPushButton("检查更新")
        self.update_btn.setObjectName("secondaryButton")
        self.update_btn.clicked.connect(self._check_update)
        about_row.addWidget(self.update_btn)

        self.update_status = QLabel("")
        self.update_status.setStyleSheet("color: #94A3B8; font-size: 12px;")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("保存")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addLayout(about_row)
        layout.addWidget(self.update_status)
        layout.addSpacing(8)
        layout.addWidget(buttons)
        self.setLayout(layout)

        self.update_checked.connect(self._on_update_checked)

    # ---------- 检查更新 ----------
    def _check_update(self):
        self.update_btn.setEnabled(False)
        self.update_status.setText("正在检查更新…")
        threading.Thread(target=self._check_update_worker, daemon=True).start()

    def _check_update_worker(self):
        self.update_checked.emit(check_for_update())

    def _on_update_checked(self, r):
        self.update_btn.setEnabled(True)
        if not r.get("ok"):
            self.update_status.setText("检查失败：" + str(r.get("error", "未知错误")))
            return
        if r.get("is_new"):
            self.update_status.setText(f"发现新版本 v{r['latest']}")
            self._ask_open_download(r)
        else:
            self.update_status.setText(f"已是最新版本 v{APP_VERSION}")

    def _ask_open_download(self, r):
        box = QMessageBox(self)
        box.setWindowTitle("发现新版本")
        box.setText(f"发现新版本 v{r['latest']}，是否前往下载？")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.button(QMessageBox.Yes).setText("去下载")
        box.button(QMessageBox.No).setText("稍后")
        box.setDefaultButton(QMessageBox.Yes)
        if box.exec() == QMessageBox.Yes:
            webbrowser.open(r["url"])

    def _save(self):
        self.config.data["detect_interval_seconds"] = self.interval_spin.value()
        self.config.data["hot_interval_seconds"] = self.hot_interval_spin.value()
        self.config.data["default_quality"] = self.quality_combo.currentText()
        self.config.data["cookie"] = self.cookie_edit.toPlainText().strip()
        self.config.data["check_update_on_start"] = self.update_check.isChecked()

        want_autostart = self.autostart_check.isChecked()
        try:
            if want_autostart and not autostart.is_enabled():
                autostart.enable()
            elif not want_autostart and autostart.is_enabled():
                autostart.disable()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "提示", str(e))

        self.config.save()
        self.accept()
