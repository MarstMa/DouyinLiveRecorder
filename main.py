"""直播录制软件入口。"""
import sys

from PySide6.QtWidgets import QApplication

from app.config import Config
from app.scheduler import Scheduler
from app.single_instance import SingleInstance
from app.ui.main_window import MainWindow
from app.ui.theme import apply_theme


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("抖音直播录制软件")
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口后仍在托盘运行

    # 只允许运行一个实例：重复启动时唤醒已有窗口，本进程直接退出
    single = SingleInstance()
    if not single.is_primary():
        return 0

    apply_theme(app)

    config = Config()
    scheduler = Scheduler(config)

    app.aboutToQuit.connect(scheduler.stop)

    window = MainWindow(config, scheduler)
    single.activate.connect(window._show_window)

    start_hidden = "--autostart" in sys.argv and config.data.get("start_minimized", False)
    if not start_hidden:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
