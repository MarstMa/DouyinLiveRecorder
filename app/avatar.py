"""头像下载：把抖音头像存到本地缓存。"""
import requests
from pathlib import Path

from .config import get_data_dir

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)


def avatar_dir() -> Path:
    d = get_data_dir() / "avatars"
    d.mkdir(parents=True, exist_ok=True)
    return d


def download_avatar(url: str, sid: str) -> str | None:
    """下载头像到本地缓存，返回路径（失败返回 None）。"""
    if not url or not sid:
        return None
    try:
        r = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=20)
        if r.status_code == 200 and r.content:
            path = avatar_dir() / f"{sid}.jpg"
            path.write_bytes(r.content)
            return str(path)
    except Exception:  # noqa: BLE001
        pass
    return None
