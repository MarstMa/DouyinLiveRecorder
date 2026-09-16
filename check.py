"""命令行检测工具：python check.py <直播间链接或抖音号> [画质]

示例：
  python check.py https://live.douyin.com/123456789
  python check.py https://live.douyin.com/123456789 高清
"""
import sys

from app.extractor import check_stream

USAGE = "用法：python check.py <直播间链接或抖音号> [画质]"


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)
    url = sys.argv[1]
    quality = sys.argv[2] if len(sys.argv) > 2 else "原画"
    print(f"检测中：{url}（画质：{quality}）…")
    r = check_stream(url, quality)
    if r.get("ok"):
        print(f"是否开播：{'是' if r.get('is_live') else '否'}")
        print(f"主播名：{r.get('anchor_name')}")
        print(f"标题：{r.get('title')}")
        print(f"FLV：{r.get('flv_url')}")
        print(f"M3U8：{r.get('m3u8_url')}")
    else:
        print(f"检测失败：{r.get('error')}")


if __name__ == "__main__":
    main()
