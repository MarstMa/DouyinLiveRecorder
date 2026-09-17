"""视频库：扫描某主播已录制的视频。"""
import re
from datetime import datetime
from pathlib import Path

from .config import Config, default_save_root


def streamer_folder(config: Config, streamer: dict) -> str:
    """返回该主播的保存文件夹（自定义优先，否则用默认目录下的主播名子目录）。"""
    name = (streamer.get("name") or "").strip() or "主播"
    return streamer.get("save_folder") or str(Path(default_save_root()) / name)


def scan_streamer_videos(config: Config, streamer: dict) -> list:
    """扫描某主播保存文件夹里的 .mp4，按日期倒序返回。

    视频 dict：path / name / date / size。
    直接扫该主播自己的文件夹，不依赖文件名格式，自定义文件名也能正确识别。
    """
    root = Path(streamer_folder(config, streamer))
    if not root.exists():
        return []

    videos = []
    for f in root.rglob("*.mp4"):
        try:
            st = f.stat()
        except OSError:
            continue
        videos.append({
            "path": str(f),
            "name": f.name,
            "date": _parse_date(f.name) or _fmt_mtime(st.st_mtime),
            "size": st.st_size,
        })

    videos.sort(key=lambda v: v["date"], reverse=True)
    return videos


def _parse_date(filename: str) -> str | None:
    """从文件名里提取 `YYYYMMDD_HHMMSS` 作为录制时间，取不到返回 None。"""
    m = re.search(r"(\d{8})[_\-\s]?(\d{6})", filename)
    if m:
        try:
            dt = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    return None


def _fmt_mtime(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def format_size(num: int) -> str:
    """字节数转人类可读大小。"""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024 or unit == "TB":
            return f"{num:.1f} {unit}" if unit != "B" else f"{num} B"
        num /= 1024
    return f"{num:.1f} TB"
