"""检查更新 / 下载更新 / 自更新（替换 exe 并重启）。"""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from .config import APP_VERSION

GITHUB_REPO = "MarstMa/DouyinLiveRecorder"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def parse_version(tag: str) -> tuple:
    """把 'v0.1' / '0.1.2' / '0.3.1' 解析成可比较的元组 (主, 次, 修订)。"""
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", tag or "")
    if not m:
        return (0, 0, 0)
    return tuple(int(x or 0) for x in m.groups())


def check_for_update(timeout: int = 10) -> dict:
    """查询最新版本。返回 {ok, latest, url, asset_url, is_new, error}。"""
    req = urllib.request.Request(API_URL, headers={"User-Agent": "DouyinLiveRecorder"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tag = data.get("tag_name", "")
        url = data.get("html_url", "")
        # 找发布里的 .exe 下载地址（用于自动更新）
        asset_url = ""
        for a in data.get("assets", []):
            if (a.get("name") or "").lower().endswith(".exe"):
                asset_url = a.get("browser_download_url", "")
                break
        is_new = parse_version(tag) > parse_version(APP_VERSION)
        return {"ok": True, "latest": tag.lstrip("v"), "url": url,
                "asset_url": asset_url, "is_new": is_new, "error": ""}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "latest": "", "url": "", "asset_url": "", "is_new": False, "error": str(e)}


def download_update(asset_url: str, dest: str, progress_cb=None) -> str:
    """下载新版 exe 到 dest，返回 dest。progress_cb(done_bytes, total_bytes)。"""
    req = urllib.request.Request(asset_url, headers={"User-Agent": "DouyinLiveRecorder"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress_cb:
                    progress_cb(done, total)
    return dest


def current_exe_path() -> str:
    """打包后返回自身 exe 的完整路径；未打包返回空串（无法自更新）。"""
    if getattr(sys, "frozen", False):
        return sys.executable
    return ""


def apply_update(new_exe_path: str) -> bool:
    """启动一个临时脚本，等本程序退出后把新 exe 替换到原位置并重启。

    仅打包环境可用；Windows 下运行中的 exe 无法直接覆盖，需要先退出再替换。
    """
    exe = current_exe_path()
    if not exe or not Path(new_exe_path).exists():
        return False

    exe_name = Path(exe).name
    script = Path(tempfile.gettempdir()) / "douyin_updater.bat"
    lines = [
        "@echo off",
        ":waitloop",
        f'tasklist /fi "IMAGENAME eq {exe_name}" 2>nul | find /i "{exe_name}" >nul',
        "if not errorlevel 1 (",
        "  timeout /t 1 /nobreak >nul",
        "  goto waitloop",
        ")",
        f'move /y "{new_exe_path}" "{exe}" >nul',
        "if errorlevel 1 ( echo Update failed. Please replace the file manually. & pause & exit /b 1 )",
        f'start "" "{exe}"',
        'del "%~f0"',
    ]
    script.write_text("\r\n".join(lines), encoding="ascii")
    subprocess.Popen(["cmd", "/c", str(script)], creationflags=CREATE_NO_WINDOW)
    return True
