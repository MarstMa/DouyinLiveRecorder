"""文件名模板：把模板字符串渲染成最终文件名（不含扩展名）。"""
import re
from datetime import datetime

from .config import DEFAULT_FILENAME_TEMPLATE

# 供界面按钮使用的变量列表（顺序即界面显示顺序）
FILENAME_VARIABLES = ["主播名", "日期", "时间", "标题", "画质"]

_SEP_CHARS = " _.-"


def _sanitize_part(s) -> str:
    """去掉文件名里的非法字符，空值保留为空串（用于跳过空变量）。"""
    return re.sub(r'[\\/:*?"<>|\r\n\t]', "_", str(s or "")).strip()


def _tidy(s: str) -> str:
    """合并连续的分隔符、去掉首尾分隔符。"""
    s = re.sub(r"[ _.\-]{2,}", lambda m: m.group(0)[0], s)
    return s.strip(_SEP_CHARS)


def render_filename(template: str, context: dict | None = None) -> str:
    """按模板渲染文件名。context 可含：主播名/标题/画质/日期/时间/now。"""
    context = context or {}
    now = context.get("now") or datetime.now()
    values = {
        "{主播名}": _sanitize_part(context.get("主播名", "")),
        "{标题}": _sanitize_part(context.get("标题", ""))[:40],
        "{画质}": _sanitize_part(context.get("画质", "")),
        "{日期}": now.strftime("%Y%m%d"),
        "{时间}": now.strftime("%H%M%S"),
    }
    result = template or ""
    for k, v in values.items():
        result = result.replace(k, v)
    result = _tidy(result)
    if not result.strip(_SEP_CHARS):
        result = render_filename(DEFAULT_FILENAME_TEMPLATE, context)
    return result


def preview_filename(template: str) -> str:
    """用示例数据生成预览文件名（供界面实时预览）。"""
    return render_filename(template, {
        "主播名": "主播示例",
        "标题": "直播标题示例",
        "画质": "原画",
    })
