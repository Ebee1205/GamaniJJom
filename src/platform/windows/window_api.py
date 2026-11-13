"""Typed Win32 calls; geometry uses the outer window rectangle in screen pixels."""
import ctypes
from ctypes import wintypes as wt

from src.models.window_schema import WindowInfo, WindowRect

user32 = ctypes.WinDLL("user32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
EnumCallback = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def _bind(dll, name, args, result):
    function = getattr(dll, name)
    function.argtypes = args
    function.restype = result
    return function


_enum = _bind(user32, "EnumWindows", [EnumCallback, wt.LPARAM], wt.BOOL)
_exists = _bind(user32, "IsWindow", [wt.HWND], wt.BOOL)
_visible = _bind(user32, "IsWindowVisible", [wt.HWND], wt.BOOL)
_iconic = _bind(user32, "IsIconic", [wt.HWND], wt.BOOL)
_zoomed = _bind(user32, "IsZoomed", [wt.HWND], wt.BOOL)
_owner = _bind(user32, "GetWindow", [wt.HWND, wt.UINT], wt.HWND)
_style = _bind(user32, "GetWindowLongW", [wt.HWND, ctypes.c_int], wt.LONG)
_length = _bind(user32, "GetWindowTextLengthW", [wt.HWND], ctypes.c_int)
_text = _bind(user32, "GetWindowTextW", [wt.HWND, wt.LPWSTR, ctypes.c_int], ctypes.c_int)
_pid = _bind(user32, "GetWindowThreadProcessId", [wt.HWND, ctypes.POINTER(wt.DWORD)], wt.DWORD)
_rect = _bind(user32, "GetWindowRect", [wt.HWND, ctypes.POINTER(wt.RECT)], wt.BOOL)
_move = _bind(user32, "SetWindowPos", [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int, wt.UINT], wt.BOOL)
_attribute = _bind(dwmapi, "DwmGetWindowAttribute",
                   [wt.HWND, wt.DWORD, wt.LPVOID, wt.DWORD], wt.LONG)


def enable_dpi_awareness() -> None:
    """Call before creating Tk windows. Respect awareness already set by a host."""
    try:
        set_context = _bind(user32, "SetProcessDpiAwarenessContext", [wt.HANDLE], wt.BOOL)
        set_context(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
    except AttributeError:
        _bind(user32, "SetProcessDPIAware", [], wt.BOOL)()


def enumerate_handles() -> list[int]:
    handles = []

    @EnumCallback
    def collect(hwnd, _):
        handles.append(int(hwnd))
        return True

    if not _enum(collect, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return handles


def is_regular_window(hwnd: int) -> bool:
    if not _exists(hwnd) or not _visible(hwnd):
        return False
    ex_style = _style(hwnd, -20)  # GWL_EXSTYLE
    if ex_style & 0x80:  # WS_EX_TOOLWINDOW
        return False
    if _owner(hwnd, 4) and not ex_style & 0x40000:  # GW_OWNER / WS_EX_APPWINDOW
        return False
    cloaked = wt.DWORD()
    result = _attribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
    return not (result == 0 and cloaked.value)


def read_window(hwnd: int) -> WindowInfo:
    if not _exists(hwnd):
        raise OSError("대상 창이 종료되었습니다. 목록을 새로고침하세요.")
    pid = wt.DWORD()
    if not _pid(hwnd, ctypes.byref(pid)):
        raise ctypes.WinError(ctypes.get_last_error())
    title = ctypes.create_unicode_buffer(max(_length(hwnd) + 1, 512))
    _text(hwnd, title, len(title))
    rect = wt.RECT()
    if not _rect(hwnd, ctypes.byref(rect)):
        raise ctypes.WinError(ctypes.get_last_error())
    return WindowInfo(hwnd, pid.value, title.value,
                      WindowRect(rect.left, rect.top, rect.right - rect.left,
                                 rect.bottom - rect.top))


def set_rect(hwnd: int, rect: WindowRect) -> None:
    if _iconic(hwnd) or _zoomed(hwnd):
        raise ValueError("최소화·최대화된 창은 일반 창으로 복원한 뒤 적용하세요.")
    # Queue cross-thread moves to avoid waiting on an unresponsive application.
    # Preserve activation and Z order: NOZORDER | NOACTIVATE | ASYNCWINDOWPOS.
    if not _move(hwnd, None, rect.x, rect.y, rect.width, rect.height, 0x4014):
        raise ctypes.WinError(ctypes.get_last_error())
