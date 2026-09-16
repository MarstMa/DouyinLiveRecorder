"""ffmpeg 录制封装：录制直播流到 .ts，下播后封装成 .mp4。"""
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def find_ffmpeg() -> str | None:
    """定位 ffmpeg.exe：环境变量 > 项目 assets > 系统 PATH。"""
    env = os.environ.get("STREAMRECORDER_FFMPEG")
    if env and Path(env).exists():
        return env

    candidates = []
    if getattr(sys, "frozen", False):
        # PyInstaller 打包后
        meipass = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidates += [
            meipass / "assets" / "ffmpeg.exe",
            Path(sys.executable).parent / "assets" / "ffmpeg.exe",
        ]
    else:
        # 开发环境：项目根 / assets
        candidates.append(Path(__file__).resolve().parent.parent / "assets" / "ffmpeg.exe")

    for c in candidates:
        if c.exists():
            return str(c)

    return shutil.which("ffmpeg")


class Recorder:
    """用 ffmpeg 录制直播流。"""

    def __init__(self, ffmpeg_path: str | None = None):
        self.ffmpeg = ffmpeg_path or find_ffmpeg()
        self.ffprobe = None
        if self.ffmpeg:
            self.ffprobe = str(Path(self.ffmpeg).with_name("ffprobe.exe"))

    @property
    def available(self) -> bool:
        return bool(self.ffmpeg and Path(self.ffmpeg).exists())

    def start(self, stream_url: str, save_folder: str, basename: str):
        """启动录制，返回 (subprocess, ts 路径)。"""
        if not self.available:
            raise RuntimeError("未找到 ffmpeg，无法录制")

        folder = Path(save_folder)
        folder.mkdir(parents=True, exist_ok=True)
        ts_path = folder / f"{basename}.ts"

        cmd = [
            self.ffmpeg, "-hide_banner", "-loglevel", "warning",
            "-rw_timeout", "30000000",
            "-protocol_whitelist", "rtmp,crypto,file,http,https,tcp,tls,udp,rtp",
            "-thread_queue_size", "1024",
            "-analyzeduration", "20000000",
            "-probesize", "10000000",
            "-fflags", "+discardcorrupt",
            "-i", stream_url,
            "-c", "copy",
            "-f", "mpegts",
            str(ts_path),
        ]
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )
        return proc, ts_path

    @staticmethod
    def stop(proc):
        """停止 ffmpeg（优雅退出，超时后强制结束）。"""
        if proc is None or proc.poll() is not None:
            return
        try:
            if proc.stdin:
                proc.stdin.write(b"q")
                proc.stdin.flush()
                proc.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                proc.kill()

    def finalize(self, ts_path: Path, save_folder: str, basename: str) -> str | None:
        """把 .ts 封装成 .mp4，成功后删除 .ts。返回 mp4 路径（失败返回 None）。"""
        ts_path = Path(ts_path)
        folder = Path(save_folder)
        mp4_path = folder / f"{basename}.mp4"
        if not ts_path.exists():
            return None

        codec = self._probe_video_codec(ts_path)
        if codec and codec.lower() in ("hevc", "h265"):
            # H.265 转 H.264，保证系统播放器能直接播放
            cmd = [
                self.ffmpeg, "-hide_banner", "-loglevel", "warning", "-y",
                "-i", str(ts_path),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac",
                str(mp4_path),
            ]
        else:
            cmd = [
                self.ffmpeg, "-hide_banner", "-loglevel", "warning", "-y",
                "-i", str(ts_path),
                "-c", "copy",
                str(mp4_path),
            ]
        try:
            r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=CREATE_NO_WINDOW)
            if r.returncode == 0 and mp4_path.exists():
                ts_path.unlink(missing_ok=True)
                return str(mp4_path)
        except Exception:  # noqa: BLE001
            pass
        return None

    def _probe_video_codec(self, path: Path) -> str | None:
        if not self.ffprobe or not Path(self.ffprobe).exists():
            return None
        cmd = [
            self.ffprobe, "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "csv=p=0",
            str(path),
        ]
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               creationflags=CREATE_NO_WINDOW, timeout=30)
            return r.stdout.decode("utf-8", "ignore").strip()
        except Exception:  # noqa: BLE001
            return None


def make_basename(anchor_name: str) -> str:
    """生成录制文件前缀：主播名_日期_时间。"""
    from .config import sanitize_filename

    name = sanitize_filename(anchor_name)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{name}_{ts}"
