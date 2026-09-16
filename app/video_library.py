"""视频库：扫描已录制的视频并按主播分组。"""
import re
from datetime import datetime
from pathlib import Path

from .config import Config, default_save_root, sanitize_filename


def collect_video_dirs(config: Config) -> list[str]:
    """返回要扫描的目录：默认保存目录 + 各主播的保存目录。"""
    dirs = {default_save_root()}
    for s in config.streamers:
        name = s.get("name") or ""
        folder = s.get("save_folder") or str(Path(default_save_root()) / name)
        if folder:
            dirs.add(folder)
    return list(dirs)


def scan_videos(config: Config) -> list:
    """扫描视频并按主播分组。

    返回 [(主播名, [视频 dict, ...]), ...]，按主播名排序，「其他」排最后；
    视频 dict：path / name / date / size。
    """
    # 主播名前缀映射（文件名前缀 -> 主播名）
    prefixes = []
    for s in config.streamers:
        name = s.get("name") or ""
        if name:
            prefixes.append((sanitize_filename(name), name))

    groups: dict[str, list] = {}
    seen = set()
    for d in collect_video_dirs(config):
        root = Path(d)
        if not root.exists():
            continue
        for f in root.rglob("*.mp4"):
            key = str(f.resolve())
            if key in seen:
                continue
            seen.add(key)
            group = _match_group(f.name, prefixes)
            groups.setdefault(group, []).append({
                "path": str(f),
                "name": f.name,
                "date": _parse_date(f.name) or _fmt_mtime(f),
                "size": f.stat().st_size,
            })

    for g in groups:
        groups[g].sort(key=lambda v: v["date"], reverse=True)

    ordered = sorted(groups.items(), key=lambda kv: (kv[0] == "其他", kv[0]))
    return ordered


def scan_streamer_videos(config: Config, streamer_name: str) -> list:
    """返回某个主播的已录视频列表（按日期倒序）。"""
    for name, videos in scan_videos(config):
        if name == streamer_name:
            return videos
    return []


def _match_group(filename: str, prefixes: list) -> str:
    for prefix, name in prefixes:
        if filename.startswith(prefix + "_"):
            return name
    if "_" in filename:
        return filename.split("_")[0]
    return "其他"


def _parse_date(filename: str) -> str | None:
    m = re.search(r"_(\d{8})_(\d{6})", filename)
    if m:
        try:
            dt = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    return None


def _fmt_mtime(f: Path) -> str:
    return datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def format_size(num: int) -> str:
    """字节数转人类可读大小。"""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024 or unit == "TB":
            return f"{num:.1f} {unit}" if unit != "B" else f"{num} B"
        num /= 1024
    return f"{num:.1f} TB"
