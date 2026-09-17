"""调度器：后台检测循环 + 多主播同时录制。"""
import threading
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .config import Config, default_save_root, sanitize_filename
from .extractor import check_stream
from .naming import DEFAULT_FILENAME_TEMPLATE, render_filename
from .recorder import Recorder


class Scheduler(QObject):
    """在后台线程轮询各主播开播状态，并驱动多个主播同时录制。"""

    # (主播id, 状态, 检测到的主播名, 错误信息)  状态: live/offline/error/disabled
    status_updated = Signal(str, str, str, str)
    # 录制状态变化（任一主播开始/停止录制）
    recording_changed = Signal()
    # 系统通知（标题, 内容）
    notify = Signal(str, str)
    # 日志文本
    log = Signal(str)

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.recorder = Recorder()
        self._thread = None
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._lock = threading.Lock()
        self._live = {}          # sid -> 最近一次检测结果（仅开播中的）
        self._recordings = {}    # sid -> {proc, ts_path, folder, basename, name}
        self._was_live = None    # 上一轮开播集合（None=首轮，用于开播提醒）
        self._last_check = {}    # sid -> 上次检测时间（用于每个主播自己的检测频率）
        self._force_scan = False # 手动扫描：本轮强制全量检测

    # ---- 对外接口（主线程调用）----
    @property
    def recording_ids(self):
        with self._lock:
            return set(self._recordings.keys())

    def is_recording(self, sid) -> bool:
        with self._lock:
            return sid in self._recordings

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.log.emit("检测已启动")

    def stop(self):
        self._stop.set()
        self._stop_all("检测已停止")
        self.log.emit("检测已停止")

    def refresh_now(self):
        """立即触发一轮全量检测（忽略每个主播自己的频率）。"""
        self._force_scan = True
        self._wake.set()

    def check_one_now(self, sid):
        """立即检测单个主播并更新其状态（用于添加/编辑后即时反馈）。"""
        threading.Thread(target=self._check_one_worker, args=(sid,), daemon=True).start()

    def manual_start(self, sid):
        """用户手动要求录制某个主播。"""
        threading.Thread(target=self._manual_start_worker, args=(sid,), daemon=True).start()

    def manual_stop(self, sid=None):
        """手动停止录制：指定 sid 则停该主播，否则停全部（后台线程执行，不卡界面）。"""
        threading.Thread(target=self._manual_stop_worker, args=(sid,), daemon=True).start()

    def _manual_stop_worker(self, sid):
        if sid is not None:
            self._stop_recording(sid, "手动停止")
        else:
            self._stop_all("手动停止")

    # ---- 后台线程 ----
    def _run(self):
        while not self._stop.is_set():
            try:
                self._cycle()
            except Exception as e:  # noqa: BLE001
                self.log.emit(f"检测循环异常：{e}")
            interval = self._base_interval()
            self._wake.wait(interval)
            self._wake.clear()

    def _base_interval(self):
        normal = max(5, int(self.config.data.get("detect_interval_seconds", 20)))
        hot = max(5, int(self.config.data.get("hot_interval_seconds", 10)))
        return min(normal, hot)

    def _effective_interval(self, s, now):
        normal = max(5, int(self.config.data.get("detect_interval_seconds", 20)))
        hot = max(5, int(self.config.data.get("hot_interval_seconds", 10)))
        if self._in_hot_period(s, now):
            return hot
        return normal

    @staticmethod
    def _in_hot_period(s, now):
        hot_start = s.get("hot_start") or ""
        hot_end = s.get("hot_end") or ""
        if not hot_start or not hot_end:
            return False
        try:
            start = datetime.strptime(hot_start, "%H:%M").time()
            end = datetime.strptime(hot_end, "%H:%M").time()
        except ValueError:
            return False
        t = now.time()
        if start <= end:
            return start <= t <= end
        return t >= start or t <= end

    def _check_one_worker(self, sid):
        s = self.config.get_streamer(sid)
        if not s or not s.get("enabled", True):
            return
        self._last_check[sid] = datetime.now()
        quality = s.get("quality") or self.config.data.get("default_quality", "原画")
        cookie = self.config.data.get("cookie") or None
        info = check_stream(s.get("url"), quality, cookie)
        if info.get("ok") and info.get("is_live"):
            with self._lock:
                self._live[sid] = info
            self.status_updated.emit(sid, "live", info.get("anchor_name") or s.get("name") or "", "")
        elif info.get("ok"):
            with self._lock:
                self._live.pop(sid, None)
            self.status_updated.emit(sid, "offline", info.get("anchor_name") or s.get("name") or "", "")
        else:
            self.status_updated.emit(sid, "error", s.get("name") or "", info.get("error") or "检测失败")

    def _manual_start_worker(self, sid):
        s = self.config.get_streamer(sid)
        if not s or not s.get("enabled", True):
            self.log.emit("该主播已停用，无法录制")
            return
        if self.is_recording(sid):
            self.log.emit(f"「{s.get('name', '')}」已在录制中")
            return
        # 优先复用后台已检测到的直播信息，避免重复请求触发风控
        with self._lock:
            info = self._live.get(sid)
        if not (info and info.get("is_live")):
            quality = s.get("quality") or self.config.data.get("default_quality", "原画")
            cookie = self.config.data.get("cookie") or None
            self.log.emit(f"正在检测「{s.get('name', '')}」是否开播…")
            info = check_stream(s.get("url"), quality, cookie)
            if not info.get("ok"):
                self.log.emit(f"「{s.get('name', '')}」检测失败：{info.get('error')}")
                return
            if not info.get("is_live"):
                self.log.emit(f"「{s.get('name', '')}」当前未开播，无法录制")
                return
        self._start_recording(sid, info)

    def _cycle(self):
        cookie = self.config.data.get("cookie") or None
        default_q = self.config.data.get("default_quality", "原画")
        now = datetime.now()
        force = self._force_scan
        self._force_scan = False

        # 1) 逐个检测开播状态（每个主播按自己的频率检测）
        for s in list(self.config.streamers):
            sid = s.get("id")
            name = s.get("name") or ""
            if not s.get("enabled", True):
                self.status_updated.emit(sid, "disabled", name, "")
                with self._lock:
                    self._live.pop(sid, None)
                continue
            interval = self._effective_interval(s, now)
            last = self._last_check.get(sid)
            if not force and last is not None and (now - last).total_seconds() < interval:
                continue  # 还没到该主播的检测时间
            self._last_check[sid] = now
            url = s.get("url", "")
            quality = s.get("quality") or default_q
            info = check_stream(url, quality, cookie)
            if info.get("ok") and info.get("is_live"):
                with self._lock:
                    self._live[sid] = info
                self.status_updated.emit(sid, "live", info.get("anchor_name") or name, "")
            elif info.get("ok"):
                with self._lock:
                    self._live.pop(sid, None)
                self.status_updated.emit(sid, "offline", info.get("anchor_name") or name, "")
            else:
                with self._lock:
                    self._live.pop(sid, None)
                err = info.get("error") or "检测失败"
                self.status_updated.emit(sid, "error", name, err)
                if "risk control" in err or "风控" in err:
                    self.notify.emit("检测可能被抖音风控", f"「{name}」检测失败：{err}")

        # 1.5) 开播提醒（用持久化的 _live 判断，避免漏掉跳过检测的主播）
        with self._lock:
            current_live = set(self._live.keys())
        if self._was_live is None:
            self._was_live = current_live
        else:
            for sid in (current_live - self._was_live):
                s = self.config.get_streamer(sid)
                name = (s.get("name") if s else "") or "主播"
                self.notify.emit("主播开播了", f"{name} 正在直播")
            self._was_live = current_live

        # 2) 停掉已下播 / 进程退出的录制
        with self._lock:
            recs = list(self._recordings.items())
            current_live = set(self._live.keys())
        for sid, r in recs:
            if sid not in current_live:
                self._stop_recording(sid, "主播已下播")
            elif r["proc"].poll() is not None:
                self._stop_recording(sid, "录制进程退出")

        # 3) 自动开始：所有开启自动录制、正在开播、且尚未录制的主播
        with self._lock:
            live_sids = list(self._live.keys())
        for sid in live_sids:
            s = self.config.get_streamer(sid)
            if s and s.get("auto_record") and not self.is_recording(sid):
                self._start_recording(sid)

    # ---- 录制控制 ----
    def _start_recording(self, sid, info=None):
        with self._lock:
            if sid in self._recordings:
                return
            if info is None:
                info = self._live.get(sid)
            s = self.config.get_streamer(sid)
        if not info:
            self.log.emit("无直播流信息，无法录制")
            return
        url = info.get("flv_url") or info.get("m3u8_url") or info.get("record_url")
        if not url:
            self.log.emit("获取直播流地址失败，无法录制")
            return
        if s is None:
            self.log.emit("主播信息不存在")
            return
        name = sanitize_filename(s.get("name") or info.get("anchor_name") or "主播")
        folder = s.get("save_folder") or str(Path(default_save_root()) / name)
        template = self.config.data.get("filename_template") or DEFAULT_FILENAME_TEMPLATE
        basename = render_filename(template, {
            "主播名": name,
            "标题": info.get("title", ""),
            "画质": s.get("quality") or self.config.data.get("default_quality", "原画"),
        })
        try:
            proc, ts_path = self.recorder.start(url, folder, basename)
        except Exception as e:  # noqa: BLE001
            self.log.emit(f"启动录制失败：{e}")
            return
        with self._lock:
            self._recordings[sid] = {
                "proc": proc, "ts_path": ts_path, "folder": folder, "basename": basename, "name": name,
            }
        self.log.emit(f"开始录制：{name} → {ts_path}")
        self.notify.emit("开始录制", f"{name} 开始录制")
        self.recording_changed.emit()

    def _stop_recording(self, sid, reason=""):
        with self._lock:
            r = self._recordings.pop(sid, None)
        if not r:
            return
        proc = r["proc"]
        ts = r["ts_path"]
        folder = r["folder"]
        basename = r["basename"]
        name = r["name"]

        self.recorder.stop(proc)
        if ts is not None:
            threading.Thread(
                target=self._finalize_bg, args=(ts, folder, basename, name, reason), daemon=True
            ).start()
        else:
            self.log.emit(f"录制结束（{reason}）：{name}")
        self.recording_changed.emit()

    def _stop_all(self, reason="手动停止"):
        with self._lock:
            sids = list(self._recordings.keys())
        for sid in sids:
            self._stop_recording(sid, reason)

    def _finalize_bg(self, ts, folder, basename, name, reason):
        mp4 = self.recorder.finalize(ts, folder, basename)
        if mp4:
            self.log.emit(f"录制完成（{reason}），已保存：{mp4}")
            self.notify.emit("录制完成", f"{name} 录制结束，已保存：{mp4}")
        else:
            self.log.emit(f"录制结束（{reason}）：{name}（视频生成失败，原始文件保留在 {ts}）")
            self.notify.emit("录制结束", f"{name} 录制结束（{reason}）")
