"""检查更新：查询 GitHub 最新 Release，和当前版本比较。"""
import json
import re
import urllib.request

from .config import APP_VERSION

GITHUB_REPO = "MarstMa/StreamerRecording"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def parse_version(tag: str) -> tuple:
    """把 'v0.1' / '0.1.2' 解析成可比较的元组 (主, 次, 修订)。"""
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", tag or "")
    if not m:
        return (0, 0, 0)
    return tuple(int(x or 0) for x in m.groups())


def check_for_update(timeout: int = 10) -> dict:
    """查询最新版本，返回 {ok, latest, url, is_new, error}。"""
    req = urllib.request.Request(API_URL, headers={"User-Agent": "StreamerRecording"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tag = data.get("tag_name", "")
        url = data.get("html_url", "")
        is_new = parse_version(tag) > parse_version(APP_VERSION)
        return {"ok": True, "latest": tag.lstrip("v"), "url": url, "is_new": is_new}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "latest": "", "url": "", "is_new": False, "error": str(e)}
