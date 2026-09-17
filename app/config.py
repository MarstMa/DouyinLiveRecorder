"""配置读写：主播列表、全局设置。"""
import json
import os
import re
import uuid
from pathlib import Path

APP_NAME = "StreamerRecording"
APP_VERSION = "0.2"

# 文件名模板默认值
DEFAULT_FILENAME_TEMPLATE = "{主播名}_{日期}_{时间}"

# 画质选项（界面显示名 -> streamget 使用的代码）
QUALITY_OPTIONS = {
    "原画": "OD",
    "超清": "UHD",
    "高清": "HD",
    "标清": "SD",
    "流畅": "LD",
}

# 录制方式
RECORD_MODES = ["截流", "录屏"]


def get_data_dir() -> Path:
    """返回配置/数据目录：%APPDATA%\\StreamerRecording。"""
    base = os.environ.get("APPDATA") or str(Path.home())
    d = Path(base) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def default_save_root() -> str:
    """默认保存根目录：用户视频目录下的「直播录制」。"""
    videos = Path.home() / "Videos"
    if videos.exists():
        return str(videos / "直播录制")
    return str(Path.home() / "直播录制")


def sanitize_filename(name: str) -> str:
    """去掉文件名里的非法字符。"""
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", str(name)).strip()
    return name or "主播"


DEFAULT_CONFIG = {
    "version": 1,
    "detect_interval_seconds": 20,
    "hot_interval_seconds": 10,
    "auto_start": False,
    "start_minimized": False,
    "check_update_on_start": True,
    "default_quality": "原画",
    "filename_template": DEFAULT_FILENAME_TEMPLATE,
    "default_record_mode": "截流",
    "cookie": "",
    "streamers": [],
}


class Config:
    """封装 config.json 的读写。"""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else get_data_dir() / "config.json"
        self.data: dict = {}
        self.load()

    def load(self):
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.data = dict(DEFAULT_CONFIG)
        else:
            self.data = dict(DEFAULT_CONFIG)
        for k, v in DEFAULT_CONFIG.items():
            self.data.setdefault(k, v)
        if not isinstance(self.data.get("streamers"), list):
            self.data["streamers"] = []

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ---- 主播列表操作 ----
    @property
    def streamers(self) -> list:
        return self.data["streamers"]

    def get_streamer(self, sid: str) -> dict | None:
        for s in self.streamers:
            if s.get("id") == sid:
                return s
        return None

    def add_streamer(self, name, url, save_folder, quality, record_mode, enabled=True, avatar="", auto_record=False, hot_start="", hot_end="") -> dict:
        s = {
            "id": uuid.uuid4().hex,
            "name": name,
            "url": url.strip(),
            "save_folder": save_folder,
            "quality": quality,
            "record_mode": record_mode,
            "enabled": bool(enabled),
            "avatar": avatar or "",
            "auto_record": bool(auto_record),
            "hot_start": hot_start or "",
            "hot_end": hot_end or "",
        }
        self.streamers.append(s)
        self.save()
        return s

    def update_streamer(self, sid, **fields):
        s = self.get_streamer(sid)
        if s:
            s.update(fields)
            self.save()

    def remove_streamer(self, sid):
        self.data["streamers"] = [s for s in self.streamers if s.get("id") != sid]
        self.save()
