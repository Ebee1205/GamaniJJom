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
    """Call before creating Tk windows. Respect awareness already set by a host."""
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