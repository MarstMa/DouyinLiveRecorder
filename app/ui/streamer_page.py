"""主播页：三级导航（卡片网格 → 主播页 → 编辑页）。"""
import os
import subprocess
import uuid
from datetime import datetime

from PySide6.QtCore import QTime, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)
from send2trash import send2trash

from ..avatar import download_avatar
from ..config import Config, QUALITY_OPTIONS, RECORD_MODES, default_save_root
from ..extractor import check_stream, get_avatar_url, normalize_input
from ..scheduler import Scheduler
from ..video_library import format_size, scan_streamer_videos

STATE = {
    "live": ("直播中", "#34D399"),
    "offline": ("未开播", "#64748B"),
    "error": ("检测失败", "#F87171"),
}
DISABLED_COLOR = "#64748B"
RECORDING_COLOR = "#F59E0B"

_AVATAR_COLORS = ["#38BDF8", "#34D399", "#F59E0B", "#F87171", "#A78BFA", "#22D3EE", "#FB923C", "#4ADE80"]


def _avatar_color(name: str) -> str:
    h = sum(ord(c) for c in (name or "?"))
    return _AVATAR_COLORS[h % len(_AVATAR_COLORS)]


def _badge_style(color: str) -> str:
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    return (
        f"background-color: rgba({r},{g},{b},0.15); color: {color}; "
        "border-radius: 9px; padding: 3px 12px; font-size: 12px; font-weight: bold;"
    )


def _relative_time(dt) -> str:
    """把时间戳转成「几秒前」的相对时间。"""
    if dt is None or not isinstance(dt, datetime):
        return ""
    delta = (datetime.now() - dt).total_seconds()
    if delta < 5:
        return "刚刚"
    if delta < 60:
        return f"{int(delta)} 秒前"
    if delta < 3600:
        return f"{int(delta // 60)} 分钟前"
    if delta < 86400:
        return f"{int(delta // 3600)} 小时前"
    return f"{int(delta // 86400)} 天前"


def circular_pixmap(path: str, size: int) -> QPixmap | None:
    pm = QPixmap(path)
    if pm.isNull():
        return None
    pm = pm.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = (pm.width() - size) // 2
    y = (pm.height() - size) // 2
    pm = pm.copy(x, y, size, size)

    out = QPixmap(size, size)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    clip = QPainterPath()
    clip.addEllipse(0, 0, size, size)
    p.setClipPath(clip)
    p.drawPixmap(0, 0, pm)
    p.end()
    return out


def apply_avatar(label: QLabel, streamer: dict, size: int):
    path = (streamer or {}).get("avatar") or ""
    label.setFixedSize(size, size)
    if path and os.path.exists(path):
        pm = circular_pixmap(path, size)
        if pm is not None:
            label.clear()
            label.setPixmap(pm)
            label.setStyleSheet("")
            return
    name = (streamer or {}).get("name") or "?"
    label.clear()
    label.setText((name.strip() or "?")[0])
    label.setAlignment(Qt.AlignCenter)
    label.setStyleSheet(
        f"background-color: {_avatar_color(name)}; color: #0F172A; "
        f"border-radius: {size // 2}px; font-size: {int(size * 0.42)}px; font-weight: bold;"
    )


class StreamerTile(QFrame):
    """网格里的方形主播卡片。"""

    clicked = Signal(str)

    def __init__(self, streamer: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("tileCard")
        self.sid = streamer.get("id")
        self._anchor = streamer.get("name", "") or "主播"
        self._auto_record = streamer.get("auto_record", False)
        self._dim = None
        self._recording = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(184, 218)

        v = QVBoxLayout(self)
        v.setContentsMargins(12, 16, 12, 12)
        v.setSpacing(8)
        v.setAlignment(Qt.AlignCenter)

        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(72, 72)
        v.addWidget(self.avatar_label, alignment=Qt.AlignHCenter)

        self.name_label = QLabel(self._anchor)
        self.name_label.setObjectName("cardName")
        self.name_label.setAlignment(Qt.AlignCenter)
        v.addWidget(self.name_label)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        v.addWidget(self.status_label)

        self.meta_label = QLabel("")
        self.meta_label.setObjectName("muted")
        self.meta_label.setStyleSheet("font-size: 11px;")
        self.meta_label.setAlignment(Qt.AlignCenter)
        v.addWidget(self.meta_label)

        apply_avatar(self.avatar_label, streamer, 72)
        self.update_state("disabled" if not streamer.get("enabled", True) else "offline", "", "", None)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.sid)
        super().mousePressEvent(event)

    def _apply_dim(self, on: bool):
        if on:
            if self._dim is None:
                self._dim = QGraphicsOpacityEffect(self)
                self._dim.setOpacity(0.55)
                self.setGraphicsEffect(self._dim)
        else:
            self.setGraphicsEffect(None)
            self._dim = None

    def update_state(self, state, anchor, error, scan_dt=None):
        self._state = state
        self._anchor_name = anchor
        self._error = error
        self._scan_dt = scan_dt
        self._refresh()

    def update_recording(self, recording):
        self._recording = recording
        self._refresh()

    def _refresh(self):
        if self._state == "disabled":
            self._apply_dim(True)
            self.status_label.setText("已停用")
            self.status_label.setStyleSheet(_badge_style(DISABLED_COLOR))
            self.name_label.setToolTip("该主播已停用，点击进入详情可重新开启")
            self.meta_label.setText("")
            return
        self._apply_dim(False)
        if self._recording:
            self.status_label.setText("录制中")
            self.status_label.setStyleSheet(_badge_style(RECORDING_COLOR))
        else:
            text, color = STATE.get(self._state, ("未知", "#64748B"))
            self.status_label.setText(text)
            self.status_label.setStyleSheet(_badge_style(color))
        self._update_meta()
        if self._state == "error" and self._error:
            self.name_label.setToolTip(f"检测失败：{self._error}")
        elif self._anchor_name and self._anchor_name != self.name_label.text():
            self.name_label.setToolTip(f"检测到的主播名：{self._anchor_name}")
        else:
            self.name_label.setToolTip("")

    def _update_meta(self):
        auto = "自动录制" if self._auto_record else "手动录制"
        parts = [auto]
        rel = _relative_time(getattr(self, "_scan_dt", None))
        if rel:
            parts.append(f"扫描 {rel}")
        self.meta_label.setText(" · ".join(parts))

    def refresh_scan_time(self):
        if self._state != "disabled":
            self._update_meta()


class StreamerOverviewView(QWidget):
    """第二级：主播页（只读概览 + 该主播的已录视频 + 操作）。"""

    back = Signal()
    edit_requested = Signal(str)
    enabled_toggled = Signal(str, bool)

    def __init__(self, config: Config, scheduler: Scheduler, streamer: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.scheduler = scheduler
        self.sid = streamer.get("id")
        self._streamer = streamer
        self._state = "offline"
        self._recording = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 4, 0)
        lay.setSpacing(12)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        # 顶部：返回 + 名字 + 状态
        header = QHBoxLayout()
        back_btn = QPushButton("← 返回")
        back_btn.setObjectName("secondaryButton")
        back_btn.clicked.connect(self.back.emit)
        name_title = QLabel(streamer.get("name", ""))
        name_title.setObjectName("appTitle")
        self.status_label = QLabel("")
        header.addWidget(back_btn)
        header.addWidget(name_title)
        header.addSpacing(8)
        header.addWidget(self.status_label)
        header.addStretch(1)
        lay.addLayout(header)

        # 头像 + 名字
        avatar_row = QHBoxLayout()
        avatar_row.setSpacing(16)
        self.avatar_label = QLabel()
        apply_avatar(self.avatar_label, streamer, 72)
        avatar_row.addWidget(self.avatar_label)
        name_box = QVBoxLayout()
        name_box.setSpacing(2)
        big_name = QLabel(streamer.get("name", ""))
        big_name.setObjectName("cardName")
        name_box.addWidget(big_name)
        name_box.addStretch(1)
        avatar_row.addLayout(name_box)
        avatar_row.addStretch(1)
        lay.addLayout(avatar_row)

        # 信息卡（只读）
        info_card = QFrame()
        info_card.setObjectName("card")
        info_form = QFormLayout(info_card)
        info_form.setSpacing(9)
        info_form.setLabelAlignment(Qt.AlignRight)

        def add_row(label, value):
            v = QLabel(str(value))
            v.setWordWrap(True)
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            info_form.addRow(f"{label}：", v)

        add_row("直播间/抖音号", streamer.get("url", ""))
        add_row("画质", streamer.get("quality", "原画"))
        add_row("保存文件夹", streamer.get("save_folder") or "默认保存")
        add_row("录制方式", streamer.get("record_mode", "截流"))
        add_row("自动录制", "开" if streamer.get("auto_record") else "关（手动录制）")
        self.enabled_check = QCheckBox("启用该主播（取消勾选即停用）")
        self.enabled_check.setChecked(streamer.get("enabled", True))
        self.enabled_check.toggled.connect(self._toggle_enabled)
        info_form.addRow("启用：", self.enabled_check)
        lay.addWidget(info_card)

        # 已录视频
        vh = QHBoxLayout()
        vt = QLabel("已录视频")
        vt.setObjectName("appTitle")
        self.videos_count = QLabel("")
        self.videos_count.setObjectName("appSubtitle")
        refresh_btn = QPushButton("刷新")
        refresh_btn.setObjectName("secondaryButton")
        refresh_btn.clicked.connect(self._refresh_videos)
        vh.addWidget(vt)
        vh.addWidget(self.videos_count)
        vh.addStretch(1)
        vh.addWidget(refresh_btn)
        lay.addLayout(vh)

        self.videos_box = QWidget()
        self.videos_layout = QVBoxLayout(self.videos_box)
        self.videos_layout.setContentsMargins(0, 0, 0, 0)
        self.videos_layout.setSpacing(8)
        lay.addWidget(self.videos_box)

        # 操作按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.start_btn = QPushButton("开始录制")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("停止录制")
        self.stop_btn.setObjectName("dangerButton")
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.hide()
        open_btn = QPushButton("打开直播间")
        open_btn.setObjectName("secondaryButton")
        open_btn.clicked.connect(self._open_live)
        edit_btn = QPushButton("编辑")
        edit_btn.setObjectName("secondaryButton")
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.sid))
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addWidget(open_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)
        lay.addStretch(1)

        self._refresh_status()
        self._refresh_videos()

    # ---------- 状态同步 ----------
    def update_status(self, state, anchor, error):
        self._state = state
        self._refresh_status()

    def update_recording(self, recording):
        self._recording = recording
        self._refresh_status()

    def _refresh_status(self):
        if not self._streamer.get("enabled", True):
            text, color = "已停用", DISABLED_COLOR
        elif self._recording:
            text, color = "录制中", RECORDING_COLOR
        else:
            text, color = STATE.get(self._state, ("未开播", "#64748B"))
        self.status_label.setText(f"● {text}")
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        if self._recording:
            self.start_btn.hide()
            self.stop_btn.show()
        else:
            self.stop_btn.hide()
            self.start_btn.show()
            self.start_btn.setEnabled(self._state == "live" and self._streamer.get("enabled", True))

    def _toggle_enabled(self, checked):
        self.config.update_streamer(self.sid, enabled=bool(checked))
        self._streamer["enabled"] = bool(checked)
        self._refresh_status()
        self.enabled_toggled.emit(self.sid, bool(checked))

    # ---------- 视频 ----------
    def _refresh_videos(self):
        while self.videos_layout.count():
            item = self.videos_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        videos = scan_streamer_videos(self.config, self._streamer)
        self.videos_count.setText(f"（{len(videos)} 个）")
        for v in videos:
            self.videos_layout.addWidget(self._build_video_row(v))
        if not videos:
            hint = QLabel("还没有录制的视频，主播开播录制后会显示在这里")
            hint.setObjectName("emptyHint")
            hint.setAlignment(Qt.AlignCenter)
            hint.setMinimumHeight(70)
            self.videos_layout.addWidget(hint)
        self.videos_layout.addStretch(1)

    def refresh_videos(self):
        """公开入口：录制结束后由调度器触发刷新视频列表。"""
        self._refresh_videos()

    def _build_video_row(self, v):
        row = QFrame()
        row.setObjectName("videoRow")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)
        info = QVBoxLayout()
        info.setSpacing(2)
        name = QLabel(v["name"])
        name.setObjectName("cardName")
        meta = QLabel(f"{v['date']} · {format_size(v['size'])}")
        meta.setObjectName("muted")
        info.addWidget(name)
        info.addWidget(meta)
        lay.addLayout(info, 1)
        play_btn = QPushButton("播放")
        play_btn.setObjectName("smallButton")
        play_btn.clicked.connect(lambda _=False, p=v["path"]: self._play(p))
        locate_btn = QPushButton("定位")
        locate_btn.setObjectName("smallButton")
        locate_btn.clicked.connect(lambda _=False, p=v["path"]: self._locate(p))
        del_btn = QPushButton("删除")
        del_btn.setObjectName("smallButtonDanger")
        del_btn.clicked.connect(lambda _=False, p=v["path"]: self._delete(p))
        lay.addWidget(play_btn)
        lay.addWidget(locate_btn)
        lay.addWidget(del_btn)
        return row

    def _play(self, path):
        try:
            os.startfile(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "提示", f"无法播放：{e}")

    def _locate(self, path):
        try:
            subprocess.Popen(["explorer", "/select," + os.path.normpath(path)])
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "提示", f"无法打开文件夹：{e}")

    def _delete(self, path):
        if QMessageBox.question(self, "确认删除", "确定把该视频删除到回收站吗？") != QMessageBox.Yes:
            return
        try:
            send2trash(path)
            self._refresh_videos()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "提示", f"删除失败：{e}")

    # ---------- 录制 ----------
    def _start(self):
        if self._state != "live":
            QMessageBox.information(self, "提示", "该主播当前未开播，无法录制")
            return
        self.scheduler.manual_start(self.sid)

    def _stop(self):
        self.scheduler.manual_stop(self.sid)

    def _open_live(self):
        url = self._streamer.get("url", "")
        if "://" not in url:
            url = "https://live.douyin.com/" + url
        try:
            os.startfile(url)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "提示", f"无法打开直播间：{e}")


class EditView(QWidget):
    """第三级：编辑页（表单 + 开关）。"""

    back = Signal()
    saved = Signal(str)    # 保存后的主播 sid
    deleted = Signal(str)  # 删除的主播 sid

    def __init__(self, config: Config, scheduler: Scheduler, streamer: dict | None, parent=None):
        super().__init__(parent)
        self.config = config
        self.scheduler = scheduler
        self.sid = streamer.get("id") if streamer else None
        self._streamer = streamer or {}
        self._avatar_path = self._streamer.get("avatar") or ""
        self._avatar_url = None

        self._build_ui()
        self._prefill()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(0, 0, 4, 0)
        root.setSpacing(14)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        # 顶部：返回 + 标题
        header = QHBoxLayout()
        back_btn = QPushButton("← 返回")
        back_btn.setObjectName("secondaryButton")
        back_btn.clicked.connect(self.back.emit)
        title = QLabel("编辑主播" if self.sid else "添加主播")
        title.setObjectName("appTitle")
        header.addWidget(back_btn)
        header.addWidget(title)
        header.addStretch(1)
        root.addLayout(header)

        # 头像
        avatar_row = QHBoxLayout()
        avatar_row.setSpacing(16)
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(72, 72)
        avatar_row.addWidget(self.avatar_label)
        avatar_info = QVBoxLayout()
        avatar_info.setSpacing(6)
        hint = QLabel("头像来自主播的抖音头像，可点「自动识别」或「更新头像」获取")
        hint.setObjectName("muted")
        hint.setStyleSheet("font-size: 12px;")
        self.update_avatar_btn = QPushButton("更新头像")
        self.update_avatar_btn.setObjectName("secondaryButton")
        self.update_avatar_btn.clicked.connect(self._update_avatar)
        avatar_info.addWidget(hint)
        avatar_info.addWidget(self.update_avatar_btn)
        avatar_info.addStretch(1)
        avatar_row.addLayout(avatar_info)
        avatar_row.addStretch(1)
        root.addLayout(avatar_row)

        # 表单
        form = QFormLayout()
        form.setSpacing(11)
        form.setLabelAlignment(Qt.AlignRight)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("给主播起个名字，如：小张")
        form.addRow("主播名：", self.name_edit)

        url_row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("直播链接 / 抖音号 / 分享短链接")
        self.auto_btn = QPushButton("自动识别")
        self.auto_btn.setObjectName("secondaryButton")
        self.auto_btn.clicked.connect(self._auto_detect)
        url_row.addWidget(self.url_edit, 1)
        url_row.addWidget(self.auto_btn)
        form.addRow("直播间/抖音号：", url_row)

        hint = QLabel("把抖音「分享 → 复制链接」的整段文字直接粘进来即可，会自动识别名字和头像。")
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        hint.setStyleSheet("font-size: 12px;")
        form.addRow("", hint)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(list(QUALITY_OPTIONS.keys()))
        form.addRow("画质：", self.quality_combo)

        folder_row = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("留空则保存到默认文件夹")
        browse_btn = QPushButton("浏览…")
        browse_btn.setObjectName("secondaryButton")
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(browse_btn)
        form.addRow("保存文件夹：", folder_row)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(RECORD_MODES)
        form.addRow("录制方式：", self.mode_combo)

        root.addLayout(form)

        # 热门开播时段（该时段扫描更快）
        self.hot_check = QCheckBox("热门开播时段（此时间段扫描更快）")
        self.hot_check.setChecked(False)
        hot_row = QHBoxLayout()
        self.hot_start = QTimeEdit()
        self.hot_start.setDisplayFormat("HH:mm")
        self.hot_end = QTimeEdit()
        self.hot_end.setDisplayFormat("HH:mm")
        to_label = QLabel("至")
        to_label.setObjectName("muted")
        hot_row.addWidget(self.hot_start)
        hot_row.addWidget(to_label)
        hot_row.addWidget(self.hot_end)
        hot_row.addStretch(1)
        hot_hint = QLabel("在热门时段内，该主播的检测频率会更高（间隔在「设置」里配置）。")
        hot_hint.setWordWrap(True)
        hot_hint.setObjectName("muted")
        hot_hint.setStyleSheet("font-size: 12px;")
        hot_box = QVBoxLayout()
        hot_box.setSpacing(4)
        hot_box.addWidget(self.hot_check)
        hot_box.addLayout(hot_row)
        hot_box.addWidget(hot_hint)
        root.addLayout(hot_box)

        # 开关
        self.auto_check = QCheckBox("自动录制（检测到开播就自动开始）")
        self.auto_check.setChecked(False)
        auto_hint = QLabel("关闭后仍会检测开播状态，但不会自动录制，需要你手动点「开始录制」。")
        auto_hint.setObjectName("muted")
        auto_hint.setStyleSheet("font-size: 12px;")

        enable_box = QVBoxLayout()
        enable_box.setSpacing(4)
        enable_box.addWidget(self.auto_check)
        enable_box.addWidget(auto_hint)
        root.addLayout(enable_box)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save)
        self.delete_btn = QPushButton("删除")
        self.delete_btn.setObjectName("dangerButton")
        self.delete_btn.clicked.connect(self._delete)
        btn_row.addWidget(save_btn)
        if self.sid:
            btn_row.addWidget(self.delete_btn)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        self.note_label = QLabel("")
        self.note_label.setObjectName("muted")
        self.note_label.setStyleSheet("font-size: 12px;")
        root.addWidget(self.note_label)
        root.addStretch(1)

    def _prefill(self):
        if not self._streamer:
            apply_avatar(self.avatar_label, {}, 72)
            return
        self.name_edit.setText(self._streamer.get("name", ""))
        self.url_edit.setText(self._streamer.get("url", ""))
        self.folder_edit.setText(self._streamer.get("save_folder", ""))
        self.quality_combo.setCurrentText(self._streamer.get("quality") or "原画")
        self.mode_combo.setCurrentText(self._streamer.get("record_mode") or "截流")
        self.auto_check.setChecked(self._streamer.get("auto_record", False))
        self.hot_check.setChecked(bool(self._streamer.get("hot_start")))
        self.hot_start.setTime(QTime.fromString(self._streamer.get("hot_start") or "19:00", "HH:mm"))
        self.hot_end.setTime(QTime.fromString(self._streamer.get("hot_end") or "23:00", "HH:mm"))
        apply_avatar(self.avatar_label, self._streamer, 72)

    # ---------- 动作 ----------
    def _browse_folder(self):
        start = self.folder_edit.text() or default_save_root()
        folder = QFileDialog.getExistingDirectory(self, "选择保存文件夹", start)
        if folder:
            self.folder_edit.setText(folder)

    def _auto_detect(self):
        url = normalize_input(self.url_edit.text())
        if not url:
            QMessageBox.information(self, "提示", "请先填写直播间链接或抖音号")
            return
        self.auto_btn.setEnabled(False)
        self.auto_btn.setText("识别中…")
        QGuiApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            info = check_stream(url)
            avatar_url = get_avatar_url(url)
        finally:
            QGuiApplication.restoreOverrideCursor()
            self.auto_btn.setEnabled(True)
            self.auto_btn.setText("自动识别")

        if info.get("ok") and info.get("anchor_name"):
            self.name_edit.setText(info["anchor_name"])
        if avatar_url:
            self._apply_avatar_url(avatar_url)
        if not info.get("ok"):
            QMessageBox.warning(self, "提示", info.get("error") or "识别失败")
        else:
            self.note_label.setText("已识别主播名" + ("和头像" if avatar_url else ""))

    def _update_avatar(self):
        url = normalize_input(self.url_edit.text())
        if not url:
            QMessageBox.information(self, "提示", "请先填写直播间链接或抖音号")
            return
        QGuiApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            avatar_url = get_avatar_url(url)
        finally:
            QGuiApplication.restoreOverrideCursor()
        if not avatar_url:
            QMessageBox.information(self, "提示", "未获取到主播头像")
            return
        self._apply_avatar_url(avatar_url)
        self.note_label.setText("已更新头像")

    def _apply_avatar_url(self, avatar_url):
        self._avatar_url = avatar_url
        tmp_sid = self.sid or ("preview_" + uuid.uuid4().hex[:8])
        path = download_avatar(avatar_url, tmp_sid)
        if path:
            self._avatar_path = path
            apply_avatar(self.avatar_label, {"avatar": path, "name": self.name_edit.text() or "?"}, 72)
        else:
            self.note_label.setText("头像下载失败")

    def _save(self):
        name = self.name_edit.text().strip()
        url = normalize_input(self.url_edit.text())
        if not url:
            QMessageBox.warning(self, "提示", "请填写直播间链接或抖音号")
            return
        if not name:
            QMessageBox.warning(self, "提示", "请填写主播名（可点「自动识别」）")
            return
        fields = {
            "name": name,
            "url": url,
            "save_folder": self.folder_edit.text().strip(),
            "quality": self.quality_combo.currentText(),
            "record_mode": self.mode_combo.currentText(),
            "auto_record": self.auto_check.isChecked(),
            "hot_start": self.hot_start.time().toString("HH:mm") if self.hot_check.isChecked() else "",
            "hot_end": self.hot_end.time().toString("HH:mm") if self.hot_check.isChecked() else "",
        }
        try:
            if self.sid:
                fields["avatar"] = self._avatar_path
                self.config.update_streamer(self.sid, **fields)
                result_sid = self.sid
            else:
                s = self.config.add_streamer(**fields)
                result_sid = s["id"]
                if self._avatar_url:
                    path = download_avatar(self._avatar_url, s["id"])
                    if path:
                        self.config.update_streamer(s["id"], avatar=path)
            self.saved.emit(result_sid)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "错误", f"保存失败：{e}")

    def _delete(self):
        if not self.sid:
            return
        name = self._streamer.get("name", "")
        if QMessageBox.question(self, "确认删除", f"确定删除主播「{name}」吗？") != QMessageBox.Yes:
            return
        self.scheduler.manual_stop(self.sid)
        self.config.remove_streamer(self.sid)
        self.deleted.emit(self.sid)


class StreamerPage(QWidget):
    def __init__(self, config: Config, scheduler: Scheduler, parent=None):
        super().__init__(parent)
        self.config = config
        self.scheduler = scheduler
        self._detect_state = {}   # sid -> (state, anchor, error)
        self._scan_time = {}      # sid -> "HH:MM:SS"
        self._tile_by_sid = {}
        self.overview_view = None
        self.edit_view = None
        self._edit_return_sid = None

        self._build_ui()
        self._connect_signals()
        self._reload_list()
        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._refresh_scan_times)
        self._scan_timer.start(30000)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # 第一级：列表页
        self.list_view = QWidget()
        list_layout = QVBoxLayout(self.list_view)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("主播列表")
        title.setObjectName("appTitle")
        self.count_label = QLabel("")
        self.count_label.setObjectName("appSubtitle")
        scan_btn = QPushButton("扫描")
        scan_btn.setObjectName("secondaryButton")
        scan_btn.clicked.connect(lambda: self.scheduler.refresh_now())
        self.log_btn = QPushButton("日志")
        self.log_btn.setObjectName("secondaryButton")
        self.log_btn.clicked.connect(self._toggle_log)
        add_btn = QPushButton("添加主播")
        add_btn.clicked.connect(self._add_streamer)
        header.addWidget(title)
        header.addWidget(self.count_label)
        header.addStretch(1)
        header.addWidget(scan_btn)
        header.addWidget(self.log_btn)
        header.addWidget(add_btn)
        list_layout.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(14)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.grid.setColumnStretch(8, 1)
        self.scroll.setWidget(self.grid_host)
        list_layout.addWidget(self.scroll, 1)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(90)
        self.log_view.hide()
        list_layout.addWidget(self.log_view)

        self.stack.addWidget(self.list_view)

    def _connect_signals(self):
        self.scheduler.log.connect(self._on_log)
        self.scheduler.status_updated.connect(self._on_status)
        self.scheduler.recording_changed.connect(self._refresh_recording)
        self.scheduler.recording_finished.connect(self._on_recording_finished)

    # ---------- 信号槽 ----------
    def _on_log(self, msg):
        self.log_view.appendPlainText(msg)
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def _on_status(self, sid, state, anchor_name, error):
        self._detect_state[sid] = (state, anchor_name, error)
        now = datetime.now()
        self._scan_time[sid] = now
        tile = self._tile_by_sid.get(sid)
        if tile:
            tile.update_state(state, anchor_name, error, now)
        if self.overview_view and self.overview_view.sid == sid:
            self.overview_view.update_status(state, anchor_name, error)
        self._resort_if_needed()

    def _on_recording_finished(self, sid):
        if self.overview_view and self.overview_view.sid == sid:
            self.overview_view.refresh_videos()

    def _refresh_recording(self):
        recording_ids = self.scheduler.recording_ids
        for sid, tile in self._tile_by_sid.items():
            tile.update_recording(sid in recording_ids)
        if self.overview_view:
            self.overview_view.update_recording(self.overview_view.sid in recording_ids)
        self._resort_if_needed()

    # ---------- 列表 ----------
    def _clear_grid(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _reload_list(self):
        self._clear_grid()
        self._tile_by_sid.clear()

        ordered = sorted(self.config.streamers, key=lambda s: self._sort_key(s["id"]))
        self._order = [s["id"] for s in ordered]
        cols = 4
        for i, s in enumerate(ordered):
            tile = StreamerTile(s)
            tile.clicked.connect(self._open_overview)
            self.grid.addWidget(tile, i // cols, i % cols)
            self._tile_by_sid[s["id"]] = tile

        for sid, (state, anchor, error) in self._detect_state.items():
            tile = self._tile_by_sid.get(sid)
            if tile:
                tile.update_state(state, anchor, error, self._scan_time.get(sid))

        self.count_label.setText(f"共 {len(self.config.streamers)} 个主播")
        if not self.config.streamers:
            hint = QLabel("还没有主播，点右上角「添加主播」开始")
            hint.setObjectName("emptyHint")
            hint.setAlignment(Qt.AlignCenter)
            hint.setMinimumHeight(200)
            self.grid.addWidget(hint, 0, 0, 1, cols)
        self._refresh_recording()

    def _toggle_log(self):
        if self.log_view.isVisible():
            self.log_view.hide()
            self.log_btn.setText("日志")
        else:
            self.log_view.show()
            self.log_btn.setText("收起日志")

    def _on_enabled_toggled(self, sid, enabled):
        if enabled:
            self._detect_state[sid] = ("offline", "", "")
        else:
            self._detect_state[sid] = ("disabled", "", "")
            self.scheduler.manual_stop(sid)  # 停用立即停止该主播的录制
        self._scan_time.pop(sid, None)
        self._reload_list()
        self.scheduler.refresh_now()
        if enabled:
            self.scheduler.check_one_now(sid)

    def _sort_key(self, sid):
        name = (self.config.get_streamer(sid) or {}).get("name", "") or ""
        if self.scheduler.is_recording(sid):
            return (0, name)
        state = self._detect_state.get(sid, ("offline", "", ""))[0]
        if state == "live":
            return (1, name)
        if state == "disabled":
            return (3, name)
        return (2, name)

    def _resort_if_needed(self):
        if not self._tile_by_sid:
            return
        new_order = sorted([s["id"] for s in self.config.streamers], key=self._sort_key)
        if new_order != getattr(self, "_order", None):
            self._reload_list()

    def _refresh_scan_times(self):
        for tile in self._tile_by_sid.values():
            tile.refresh_scan_time()

    # ---------- 导航 ----------
    def _add_streamer(self):
        self._open_edit(None)

    def _open_overview(self, sid):
        streamer = self.config.get_streamer(sid)
        if not streamer:
            return
        self._close_sub_views()
        view = StreamerOverviewView(self.config, self.scheduler, streamer)
        view.back.connect(self._show_list)
        view.edit_requested.connect(self._open_edit)
        view.enabled_toggled.connect(self._on_enabled_toggled)
        self.stack.addWidget(view)
        self.stack.setCurrentWidget(view)
        self.overview_view = view
        state, anchor, error = self._detect_state.get(sid, ("offline", "", ""))
        view.update_status(state, anchor, error)
        view.update_recording(self.scheduler.is_recording(sid))

    def _open_edit(self, sid):
        self._edit_return_sid = sid
        streamer = self.config.get_streamer(sid) if sid else None
        self._close_sub_views()
        view = EditView(self.config, self.scheduler, streamer)
        view.saved.connect(self._on_edit_saved)
        view.deleted.connect(self._on_edit_deleted)
        view.back.connect(self._on_edit_back)
        self.stack.addWidget(view)
        self.stack.setCurrentWidget(view)
        self.edit_view = view

    def _close_sub_views(self):
        for w in (self.overview_view, self.edit_view):
            if w:
                self.stack.removeWidget(w)
                w.deleteLater()
        self.overview_view = None
        self.edit_view = None

    def _show_list(self):
        self._close_sub_views()
        self._reload_list()
        self.stack.setCurrentWidget(self.list_view)

    def _on_edit_saved(self, result_sid):
        self._reload_list()
        self.scheduler.refresh_now()
        self.scheduler.check_one_now(result_sid)
        if self._edit_return_sid:
            self._open_overview(result_sid)
        else:
            self._show_list()

    def _on_edit_deleted(self, sid):
        self._reload_list()
        self._show_list()

    def _on_edit_back(self):
        if self._edit_return_sid:
            self._open_overview(self._edit_return_sid)
        else:
            self._show_list()
