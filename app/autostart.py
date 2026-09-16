"""开机自启：写入用户级注册表 Run 键。"""
import sys
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "StreamerRecording"


def _launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --autostart'
    python = sys.executable
    main_py = Path(__file__).resolve().parent.parent / "main.py"
    return f'"{python}" "{main_py}" --autostart'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except FileNotFoundError:
        return False
    except Exception:  # noqa: BLE001
        return False


def enable():
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, _launch_command())
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"设置开机自启失败: {e}")


def disable():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, APP_NAME)
    except FileNotFoundError:
        pass
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"取消开机自启失败: {e}")
