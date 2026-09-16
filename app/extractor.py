"""抓流模块：封装 streamget，统一对外接口（独立成易替换模块）。

支持三种输入：
  1. 直播间链接 live.douyin.com/<数字>   —— 最稳定
  2. 分享短链接 v.douyin.com/xxx         —— 自动跳转解析
  3. 抖音号（如 yall1102）              —— 通过重定向判断是否开播
"""
import asyncio
import re

import requests
from streamget import DouyinLiveStream

from .config import QUALITY_OPTIONS

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)

GUIDE_HINT = "建议在抖音里打开该主播的直播间，点「分享 → 复制链接」后粘贴直播链接（live.douyin.com 或 v.douyin.com 开头）"


def normalize_input(text: str) -> str:
    """从任意粘贴文本里提取抖音链接或抖音号。"""
    text = (text or "").strip()
    if not text:
        return ""
    m = re.search(r"https?://[^\s]+", text)
    if m:
        url = m.group(0)
        url = re.split(r"[一-鿿]", url)[0]
        return url.rstrip('，。！？、；：,.;:)）】》"\'')
    tokens = re.findall(r"[A-Za-z0-9_.-]+", text)
    if tokens:
        return tokens[-1]
    return text


def check_stream(url: str, quality: str = "原画", cookies: str | None = None) -> dict:
    """检测单个主播的开播状态并获取直播流地址。

    返回 dict：ok / is_live / anchor_name / title / flv_url / m3u8_url / record_url / error
    """
    url = normalize_input(url)
    if not url:
        return _err("未填写直播间链接或抖音号")
    if "://" in url and "douyin.com" not in url and "iesdouyin.com" not in url:
        return _err("这看起来不是抖音链接，请粘贴抖音直播间的分享链接或抖音号")
    code = QUALITY_OPTIONS.get(quality, "OD")
    try:
        result = asyncio.run(_async_check(url, code, cookies))
        return result
    except Exception as e:  # noqa: BLE001
        return _err(f"检测失败：{e}\n{GUIDE_HINT}")


async def _async_check(url: str, code: str, cookies: str | None) -> dict:
    ds = DouyinLiveStream(cookies=cookies or None)
    web_rid = _resolve_web_rid(url)
    if web_rid:
        json_data = await ds.fetch_web_stream_data(f"https://live.douyin.com/{web_rid}")
    elif _douyin_id_tail(url):
        # 抖音号：解析页面获取房间状态（开播/未开播都能正确判断）
        json_data = await ds.fetch_web_stream_data_v1(_to_url(url))
    else:
        json_data = await ds.fetch_app_stream_data(_to_url(url))

    stream = await ds.fetch_stream_url(json_data, video_quality=code)
    return {
        "ok": True,
        "is_live": bool(stream.is_live),
        "anchor_name": stream.anchor_name,
        "title": stream.title,
        "flv_url": stream.flv_url,
        "m3u8_url": stream.m3u8_url,
        "record_url": stream.record_url,
        "error": None,
    }


def get_avatar_url(url: str, cookies: str | None = None) -> str | None:
    """获取主播的抖音头像 URL。解析失败返回 None。"""
    url = normalize_input(url)
    if not url:
        return None
    try:
        return asyncio.run(_async_avatar(url, cookies))
    except Exception:  # noqa: BLE001
        return None


async def _async_avatar(url: str, cookies: str | None) -> str | None:
    ds = DouyinLiveStream(cookies=cookies or None)
    web_rid = _resolve_web_rid(url)
    if web_rid:
        raw = await ds.fetch_web_stream_data(f"https://live.douyin.com/{web_rid}", process_data=False)
        user = (raw or {}).get("data", {}).get("user") or {}
    elif _douyin_id_tail(url):
        # 抖音号未开播：从页面里提取头像
        html = _fetch_html(_to_url(url))
        return _extract_avatar_from_html(html)
    else:
        raw = await ds.fetch_app_stream_data(_to_url(url), process_data=False)
        user = (raw or {}).get("data", {}).get("room", {}).get("owner") or {}

    for key in ("avatar_thumb", "avatar_larger", "avatar_medium"):
        url_list = (user.get(key) or {}).get("url_list") or []
        if url_list:
            return url_list[0]
    return None


def _to_url(url: str) -> str:
    return url if "://" in url else "https://live.douyin.com/" + url


def _douyin_id_tail(url: str) -> str | None:
    """若输入是「抖音号」（裸抖音号或 live.douyin.com/<抖音号>），返回该抖音号，否则 None。"""
    if "://" in url:
        m = re.match(r"https?://live\.douyin\.com/([A-Za-z0-9_.-]+)/?$", url)
        return m.group(1) if m else None
    if re.match(r"^[A-Za-z0-9_.-]+$", url):
        return url
    return None


def _resolve_web_rid(url: str) -> str | None:
    """把「纯数字」或「live.douyin.com/<数字>」解析成 web_rid，其它返回 None。"""
    if url.isdigit():
        return url
    m = re.search(r"live\.douyin\.com/(\d+)", url)
    if m:
        return m.group(1)
    return None


def _fetch_html(url: str) -> str | None:
    try:
        r = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=15, allow_redirects=True)
        if r.status_code == 200:
            return r.text
    except Exception:  # noqa: BLE001
        pass
    return None


def _extract_nickname(html: str | None) -> str | None:
    """从页面里提取第一个真实的昵称。"""
    if not html:
        return None
    for m in re.finditer(r'nickname\\?":\s*\\?"([^"\\]+)', html):
        name = m.group(1)
        if name and name != "$undefined":
            return name
    return None


def _extract_avatar_from_html(html: str | None) -> str | None:
    """从页面里提取头像 URL（best-effort）。"""
    if not html:
        return None
    m = re.search(r'https://[^"\\\s]*aweme-avatar[^"\\\s]*', html)
    return m.group(0) if m else None


def _err(msg: str) -> dict:
    return {
        "ok": False,
        "is_live": False,
        "anchor_name": None,
        "title": None,
        "flv_url": None,
        "m3u8_url": None,
        "record_url": None,
        "error": msg,
    }
