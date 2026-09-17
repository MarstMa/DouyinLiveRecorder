"""自动更新流程：确认 → 下载（带进度）→ 替换 exe 并重启。"""
import tempfile
import threading
import webbrowser
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from ..updater import apply_update, current_exe_path, download_update


def prompt_and_update(parent, version: str, asset_url: str, url: str):
    """询问用户并执行自动更新。

    未打包（开发环境）或没有可下载的 exe 时，退回「去下载」网页。
    """
    # 无法自更新（开发环境 / 发布里没有 exe），退回打开网页
    if not current_exe_path() or not asset_url:
        box = QMessageBox(parent)
        box.setWindowTitle("发现新版本")
        box.setText(f"发现新版本 v{version}，是否前往下载？")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.button(QMessageBox.Yes).setText("去下载")
        box.button(QMessageBox.No).setText("稍后")
        box.setDefaultButton(QMessageBox.Yes)
        if box.exec() == QMessageBox.Yes:
            webbrowser.open(url)
        return

    box = QMessageBox(parent)
    box.setWindowTitle("发现新版本")
    box.setText(f"发现新版本 v{version}，是否立即下载并更新？")
    box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    box.button(QMessageBox.Yes).setText("立即更新")
    box.button(QMessageBox.No).setText("稍后")
    box.setDefaultButton(QMessageBox.Yes)
    if box.exec() != QMessageBox.Yes:
        return

    dest = str(Path(tempfile.gettempdir()) / f"DouyinLiveRecorder-{version}.exe")

    progress = QProgressDialog("正在下载新版本…", "取消", 0, 100, parent)
    progress.setWindowTitle("更新")
    progress.setWindowModality(Qt.WindowModal)
    progress.setMinimumDuration(0)
    progress.setValue(0)

    worker = _Downloader(asset_url, dest, parent=progress)
    progress.canceled.connect(worker.cancel)
    worker.progress.connect(lambda done, total: _on_progress(progress, done, total))
    worker.finished.connect(lambda status, msg: _on_finished(parent, progress, status, msg))
    threading.Thread(target=worker.run, daemon=True).start()


class _Downloader(QObject):
    progress = Signal(int, int)
    finished = Signal(str, str)  # (status, msg)  status: ok / error / cancel

    def __init__(self, asset_url: str, dest: str, parent=None):
        super().__init__(parent)
        self.asset_url = asset_url
        self.dest = dest
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            download_update(self.asset_url, self.dest, self._progress_cb)
            if self._cancel:
                self.finished.emit("cancel", "")
            else:
                self.finished.emit("ok", self.dest)
        except Exception as e:  # noqa: BLE001
            self.finished.emit("error", str(e))

    def _progress_cb(self, done, total):
        if self._cancel:
            return
        self.progress.emit(done, total)


def _on_progress(progress: QProgressDialog, done: int, total: int):
    if total > 0:
        pct = max(0, min(100, int(done * 100 / total)))
        progress.setRange(0, 100)
        progress.setValue(pct)
    else:
        progress.setRange(0, 0)  # 未知大小：显示为不确定进度


def _on_finished(parent, progress: QProgressDialog, status: str, msg: str):
    progress.close()
    if status == "ok":
        if apply_update(msg):
            QApplication.instance().quit()
    elif status == "error":
        QMessageBox.warning(parent, "更新失败", f"下载更新失败：{msg}")
    # status == "cancel"：什么都不做
