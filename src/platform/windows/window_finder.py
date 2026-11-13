"""Discover visible, titled application windows; tolerate windows closing mid-scan."""
from src.models.window_schema import WindowInfo
from src.platform.windows import window_api


def _is_listable(info: WindowInfo, excluded_pid: int) -> bool:
    return (info.pid != excluded_pid
            and bool(info.title.strip())
            and info.rect.width > 0
            and info.rect.height > 0)


def _sort_key(info: WindowInfo) -> tuple[str, int]:
    return (info.title.casefold(), info.hwnd)


def find_windows(excluded_pid: int) -> list[WindowInfo]:
    windows = []
    for hwnd in window_api.enumerate_handles():
        try:
            if not window_api.is_regular_window(hwnd):
                continue
            info = window_api.read_window(hwnd)
        except OSError:  # 스캔 도중 창이 닫힌 경우
            continue
        if _is_listable(info, excluded_pid):
            windows.append(info)
    return sorted(windows, key=_sort_key)