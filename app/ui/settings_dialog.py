"""全局设置对话框。"""
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
)

from .. import autostart
from ..config import QUALITY_OPTIONS


class SettingsDialog(QDialog):
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

        about = QLabel("版本：0.1 · 作者：MarstMa")
        about.setStyleSheet("color: #94A3B8; font-size: 12px;")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("保存")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(about)
        layout.addSpacing(8)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _save(self):
        self.config.data["detect_interval_seconds"] = self.interval_spin.value()
        self.config.data["hot_interval_seconds"] = self.hot_interval_spin.value()
        self.config.data["default_quality"] = self.quality_combo.currentText()
        self.config.data["cookie"] = self.cookie_edit.toPlainText().strip()

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
