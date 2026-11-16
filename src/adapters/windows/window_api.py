"""Typed Win32 calls; geometry uses the outer window rectangle in screen pixels."""
import ctypes
from ctypes import wintypes as wt

import src.models.window_enum  as window_enum
import src.models.window_schema as window_schema

# Queue cross-thread moves to avoid waiting on an unresponsive application,
# and preserve activation and Z order.
MOVE_FLAGS = (
    window_enum.SetWindowPosFlag.NOZORDER
    | window_enum.SetWindowPosFlag.NOACTIVATE
    | window_enum.SetWindowPosFlag.ASYNCWINDOWPOS
)
MIN_TITLE_BUFFER = 512

# ---- Win32 bindings --------------------------------------------------------
user32 = ctypes.WinDLL("user32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
EnumCallback = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def _bind(dll, name, args, result):
    function = getattr(dll, name)
    function.argtypes = args
    function.restype = result
    return function


_enum_windows = _bind(user32, "EnumWindows", [EnumCallback, wt.LPARAM], wt.BOOL)
_is_window = _bind(user32, "IsWindow", [wt.HWND], wt.BOOL)
_is_window_visible = _bind(user32, "IsWindowVisible", [wt.HWND], wt.BOOL)
_is_iconic = _bind(user32, "IsIconic", [wt.HWND], wt.BOOL)
_is_zoomed = _bind(user32, "IsZoomed", [wt.HWND], wt.BOOL)
_get_window = _bind(user32, "GetWindow", [wt.HWND, wt.UINT], wt.HWND)
_get_window_long = _bind(user32, "GetWindowLongW", [wt.HWND, ctypes.c_int], wt.LONG)
_get_text_length = _bind(user32, "GetWindowTextLengthW", [wt.HWND], ctypes.c_int)
_get_text = _bind(user32, "GetWindowTextW", [wt.HWND, wt.LPWSTR, ctypes.c_int], ctypes.c_int)
_get_process_id = _bind(user32, "GetWindowThreadProcessId",
                        [wt.HWND, ctypes.POINTER(wt.DWORD)], wt.DWORD)
_get_window_rect = _bind(user32, "GetWindowRect", [wt.HWND, ctypes.POINTER(wt.RECT)], wt.BOOL)
_set_window_pos = _bind(user32, "SetWindowPos",
                        [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                         ctypes.c_int, ctypes.c_int, wt.UINT], wt.BOOL)
_get_dwm_attribute = _bind(dwmapi, "DwmGetWindowAttribute",
                           [wt.HWND, wt.DWORD, wt.LPVOID, wt.DWORD], wt.LONG)


def _last_error() -> OSError:
    return ctypes.WinError(ctypes.get_last_error())


def enable_dpi_awareness() -> None:
    """Call before QApplication. Respect awareness already set by a host."""
    try:
        set_context = _bind(user32, "SetProcessDpiAwarenessContext", [wt.HANDLE], wt.BOOL)
        set_context(ctypes.c_void_p(window_enum.DpiAwarenessContext.PER_MONITOR_AWARE_V2))
    except AttributeError:
        _bind(user32, "SetProcessDPIAware", [], wt.BOOL)()


def enumerate_handles() -> list[int]:
    handles = []

    @EnumCallback
    def collect(hwnd, _):
        handles.append(int(hwnd))
        return True

    if not _enum_windows(collect, 0):
        raise _last_error()
    return handles


def _is_cloaked(hwnd: int) -> bool:
    cloaked = wt.DWORD()
    result = _get_dwm_attribute(hwnd, window_enum.DwmWindowAttribute.CLOAKED, ctypes.byref(cloaked),
                                ctypes.sizeof(cloaked))
    return result == 0 and bool(cloaked.value)


def is_regular_window(hwnd: int) -> bool:
    if not _is_window(hwnd) or not _is_window_visible(hwnd):
        return False
    ex_style = _get_window_long(hwnd, window_enum.WindowLongIndex.EXTENDED_STYLE)
    if ex_style & window_enum.WindowExtendedStyle.TOOLWINDOW:
        return False
    if _get_window(hwnd, window_enum.GetWindowCommand.OWNER) and not (
        ex_style & window_enum.WindowExtendedStyle.APPWINDOW
    ):
        return False
    return not _is_cloaked(hwnd)


def _read_title(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(max(_get_text_length(hwnd) + 1, MIN_TITLE_BUFFER))
    _get_text(hwnd, buffer, len(buffer))
    return buffer.value


def read_window(hwnd: int) -> window_schema.WindowInfo:
    if not _is_window(hwnd):
        raise OSError("대상 창이 종료되었습니다. 목록을 새로고침하세요.")
    pid = wt.DWORD()
    if not _get_process_id(hwnd, ctypes.byref(pid)):
        raise _last_error()
    rect = wt.RECT()
    if not _get_window_rect(hwnd, ctypes.byref(rect)):
        raise _last_error()
    return window_schema.WindowInfo(hwnd, pid.value, _read_title(hwnd),
                      window_schema.WindowRect(rect.left, rect.top,
                                 rect.right - rect.left, rect.bottom - rect.top))


def set_rect(hwnd: int, rect: window_schema.WindowRect) -> None:
    if _is_iconic(hwnd) or _is_zoomed(hwnd):
        raise ValueError("최소화·최대화된 창은 일반 창으로 복원한 뒤 적용하세요.")
    if not _set_window_pos(
        hwnd, None, rect.x, rect.y, rect.width, rect.height, int(MOVE_FLAGS)
    ):
        raise _last_error()


def lock_size(hwnd: int, rect: window_schema.WindowRect) -> None:
    """Lock window size only; prevent any movement."""
    if _is_iconic(hwnd) or _is_zoomed(hwnd):
        raise ValueError("최소화·최대화된 창은 일반 창으로 복원한 뒤 적용하세요.")
    lock_flags = (
        window_enum.SetWindowPosFlag.NOMOVE
        | window_enum.SetWindowPosFlag.NOZORDER
        | window_enum.SetWindowPosFlag.NOACTIVATE
        | window_enum.SetWindowPosFlag.ASYNCWINDOWPOS
    )
    if not _set_window_pos(
        hwnd, None, 0, 0, rect.width, rect.height, int(lock_flags)
    ):
        raise _last_error()


_get_foreground = _bind(user32, "GetForegroundWindow", [], wt.HWND)
_get_ancestor = _bind(user32, "GetAncestor", [wt.HWND, wt.UINT], wt.HWND)
_window_from_point = _bind(user32, "WindowFromPoint", [wt.POINT], wt.HWND)
_get_cursor_pos = _bind(user32, "GetCursorPos", [ctypes.POINTER(wt.POINT)], wt.BOOL)
_get_async_key_state = _bind(user32, "GetAsyncKeyState", [ctypes.c_int], wt.SHORT)


def foreground_window() -> int:
    return int(_get_foreground() or 0)


def is_minimized(hwnd: int) -> bool:
    return bool(_is_iconic(hwnd))


def is_maximized(hwnd: int) -> bool:
    return bool(_is_zoomed(hwnd))


def is_visible(hwnd: int) -> bool:
    return bool(_is_window_visible(hwnd)) and not _is_cloaked(hwnd)


def key_down(key: int) -> bool:
    return bool(_get_async_key_state(key) & 0x8000)


def window_at_cursor() -> int:
    point = wt.POINT()
    if not _get_cursor_pos(ctypes.byref(point)):
        raise _last_error()
    hwnd = _window_from_point(point)
    return int(_get_ancestor(hwnd, 2) or hwnd or 0)  # GA_ROOT


def place_toolbar(hwnd: int, x: int, y: int) -> None:
    """Native pixels avoid mixing Qt logical coordinates on mixed DPI monitors."""
    flags = int(MOVE_FLAGS) | 0x0001  # SWP_NOSIZE
    if not _set_window_pos(hwnd, None, x, y, 0, 0, flags):
        raise _last_error()


class MonitorInfo(ctypes.Structure):
    _fields_ = [("size", wt.DWORD), ("monitor", wt.RECT), ("work", wt.RECT),
                ("flags", wt.DWORD)]


_monitor_from_window = _bind(user32, "MonitorFromWindow", [wt.HWND, wt.DWORD], wt.HANDLE)
_get_monitor_info = _bind(user32, "GetMonitorInfoW",
                         [wt.HANDLE, ctypes.POINTER(MonitorInfo)], wt.BOOL)


def monitor_bounds(hwnd: int, *, work: bool = True) -> window_schema.WindowRect:
    info = MonitorInfo()
    info.size = ctypes.sizeof(info)
    monitor = _monitor_from_window(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
    if not _get_monitor_info(monitor, ctypes.byref(info)):
        raise _last_error()
    r = info.work if work else info.monitor
    return window_schema.WindowRect(r.left, r.top, r.right - r.left, r.bottom - r.top)
