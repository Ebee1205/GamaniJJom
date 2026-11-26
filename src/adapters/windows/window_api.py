"""Typed Win32 calls; geometry uses the outer window rectangle in screen pixels."""
import ctypes
from ctypes import wintypes as wt

from src.models.toolbar_schema import MonitorGeometry

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


def cursor_position() -> tuple[int, int]:
    point = wt.POINT()
    if not _get_cursor_pos(ctypes.byref(point)):
        raise _last_error()
    return point.x, point.y


def set_taskbar_visible(hwnd: int, enabled: bool) -> None:
    """Register the existing toolbar HWND with the Shell, without changing its style."""
    import pythoncom
    from win32com.shell import shell

    try:
        taskbar = pythoncom.CoCreateInstance(
            shell.CLSID_TaskbarList, None, pythoncom.CLSCTX_INPROC_SERVER,
            shell.IID_ITaskbarList,
        )
        taskbar.HrInit()
        if enabled:
            taskbar.AddTab(hwnd)
        else:
            taskbar.DeleteTab(hwnd)
    except pythoncom.com_error as error:
        raise OSError(f"Taskbar registration failed: {error}") from error


def _position_error(operation, hwnd, after=None):
    code = ctypes.get_last_error()
    context = f"{operation} hwnd={hwnd:#x} after={after}"
    if not code:
        return OSError(f"{context}: Win32 returned FALSE without an error code")
    error = ctypes.WinError(code)
    error.strerror = f"{error.strerror} [{context}]"
    error.args = (error.errno, error.strerror)
    return error


def set_toolbar_order(hwnd: int, *, topmost: bool, target: int | None = None) -> bool:
    """Track relative order without activating the target or raising the pair.

    Some external predecessor HWNDs reject relative insertion with error 5.
    Keep the existing non-topmost order in that case. When the target itself
    becomes foreground, raising our own toolbar to HWND_TOP needs no foreign
    insertion handle. False means relative ordering was restricted, not a move
    failure. Never promote a background target here.
    """
    # Preserve native owner/owned-window ordering when moving the toolbar.
    flags = 0x0001 | 0x0002 | 0x0010  # NOSIZE, NOMOVE, NOACTIVATE

    def place(after, operation):
        ctypes.set_last_error(0)
        if not _set_window_pos(hwnd, after, 0, 0, 0, 0, flags):
            raise _position_error(operation, hwnd, after)

    if topmost:
        place(-1, "toolbar-topmost")  # HWND_TOPMOST
        return True
    if target is not None and not _is_window(target):
        raise window_schema.WindowClosedError("Attached target has closed during Z-order update.")
    target_topmost = target and bool(_get_window_long(target, -20) & 0x8)
    if not target_topmost and _get_window_long(hwnd, -20) & 0x8:
        place(-2, "toolbar-demote")  # HWND_NOTOPMOST
    if target and _is_window(target):
        previous = int(_get_window(target, 3) or 0)  # GW_HWNDPREV
        if previous and not target_topmost and _get_window_long(previous, -20) & 0x8:
            previous = 0  # Top of the non-topmost band, below any topmost windows.
        if previous != hwnd:
            try:
                place(previous, "toolbar-relative-order")
            except OSError as error:
                if getattr(error, "winerror", None) != 5:
                    raise
                if foreground_window() == target:
                    place(0, "toolbar-above-foreground-target")
                    return True
                return False
    elif not target:
        place(-2, "toolbar-demote")
    return True


def bring_attached_pair(hwnd: int, target: int) -> bool:
    """One user-requested activation; ordinary tracking must not call this.

    Do not restore minimized targets or change their TOPMOST style. Windows may
    deny a foreground request; preserve the connection without forcing focus.
    """
    if not _is_window(target):
        raise window_schema.WindowClosedError("Attached target has closed.")
    if is_minimized(target) or not is_visible(target):
        return False
    if foreground_window() != target:
        _set_foreground(target)
    if foreground_window() != target:
        return False
    set_toolbar_order(hwnd, topmost=False, target=target)
    return True


class _MonitorInfoEx(ctypes.Structure):
    _fields_ = [("size", wt.DWORD), ("monitor", wt.RECT), ("work", wt.RECT),
                ("flags", wt.DWORD), ("device", wt.WCHAR * 32)]


def _monitor_geometry(handle) -> MonitorGeometry:
    info = _MonitorInfoEx()
    info.size = ctypes.sizeof(info)
    get_info = _bind(user32, "GetMonitorInfoW", [wt.HANDLE, wt.LPVOID], wt.BOOL)
    if not get_info(handle, ctypes.byref(info)):
        raise _last_error()
    get_scale = _bind(ctypes.WinDLL("shcore"), "GetScaleFactorForMonitor",
                      [wt.HANDLE, ctypes.POINTER(ctypes.c_int)], wt.LONG)
    scale = ctypes.c_int()
    result = get_scale(handle, ctypes.byref(scale))
    if result != 0:
        raise OSError(f"Monitor scale query failed: {result}")

    def rect(r):
        return window_schema.WindowRect(r.left, r.top, r.right - r.left, r.bottom - r.top)

    return MonitorGeometry(info.device, rect(info.monitor), rect(info.work), scale.value / 100)


def monitor_at(x: int, y: int) -> MonitorGeometry:
    get_monitor = _bind(user32, "MonitorFromPoint", [wt.POINT, wt.DWORD], wt.HANDLE)
    return _monitor_geometry(get_monitor(wt.POINT(x, y), 2))


def available_monitors() -> list[MonitorGeometry]:
    monitors = []
    callback_type = ctypes.WINFUNCTYPE(wt.BOOL, wt.HANDLE, wt.HDC,
                                      ctypes.POINTER(wt.RECT), wt.LPARAM)
    error = []

    @callback_type
    def collect(handle, _dc, _rect, _data):
        try:
            monitors.append(_monitor_geometry(handle))
        except OSError as failure:
            error.append(failure)
            return False
        return True

    enum = _bind(user32, "EnumDisplayMonitors", [wt.HDC, wt.LPVOID, callback_type, wt.LPARAM], wt.BOOL)
    if not enum(None, None, collect, 0):
        raise error[0] if error else _last_error()
    # MONITOR_DEFAULTTOPRIMARY gives the primary monitor for this offscreen rect.
    primary = _monitor_geometry(_monitor_from_window(None, 1))
    return sorted(monitors, key=lambda monitor: monitor.device != primary.device)

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
_get_class_name = _bind(user32, "GetClassNameW", [wt.HWND, wt.LPWSTR, ctypes.c_int], ctypes.c_int)
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
    class_name = ctypes.create_unicode_buffer(256)
    _get_class_name(hwnd, class_name, len(class_name))
    if class_name.value in ('Progman', 'WorkerW', 'Shell_TrayWnd', 'Shell_SecondaryTrayWnd'):
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


def _visible_rect(hwnd: int) -> wt.RECT:
    """Visible frame excluding the DWM drop shadow; falls back to GetWindowRect."""
    rect = wt.RECT()
    if _get_dwm_attribute(hwnd, window_enum.DwmWindowAttribute.EXTENDED_FRAME_BOUNDS,
                          ctypes.byref(rect), ctypes.sizeof(rect)) == 0:
        return rect
    if not _get_window_rect(hwnd, ctypes.byref(rect)):
        raise _last_error()
    return rect


def capture_bounds(hwnd: int) -> tuple[window_schema.WindowRect, window_schema.WindowRect]:
    """Return the outer PrintWindow bounds and the visible DWM frame in screen pixels."""
    outer = wt.RECT()
    if not _get_window_rect(hwnd, ctypes.byref(outer)):
        raise _last_error()
    visible = _visible_rect(hwnd)

    def as_rect(rect):
        return window_schema.WindowRect(
            rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
        )

    return as_rect(outer), as_rect(visible)


def _shadow_inset(hwnd: int) -> tuple[int, int, int, int]:
    """Shadow thickness (left, top, right, bottom) between the outer and visible rects."""
    outer = wt.RECT()
    if not _get_window_rect(hwnd, ctypes.byref(outer)):
        raise _last_error()
    visible = _visible_rect(hwnd)
    return (visible.left - outer.left, visible.top - outer.top,
            outer.right - visible.right, outer.bottom - visible.bottom)


def read_window(hwnd: int) -> window_schema.WindowInfo:
    if not _is_window(hwnd):
        raise window_schema.WindowClosedError("대상 창이 종료되었습니다. 목록을 새로고침하세요.")
    pid = wt.DWORD()
    if not _get_process_id(hwnd, ctypes.byref(pid)):
        raise _last_error()
    rect = _visible_rect(hwnd)
    title = _read_title(hwnd)
    confirmed_pid = wt.DWORD()
    if not _is_window(hwnd):
        raise window_schema.WindowClosedError("Target window closed during inspection.")
    if not _get_process_id(hwnd, ctypes.byref(confirmed_pid)):
        raise _last_error()
    if confirmed_pid.value != pid.value:
        raise window_schema.WindowClosedError("Target window identity changed during inspection.")
    return window_schema.WindowInfo(hwnd, pid.value, title,
                      window_schema.WindowRect(rect.left, rect.top,
                                 rect.right - rect.left, rect.bottom - rect.top))


def set_rect(hwnd: int, rect: window_schema.WindowRect) -> None:
    if _is_iconic(hwnd) or _is_zoomed(hwnd):
        raise ValueError("최소화·최대화된 창은 일반 창으로 복원한 뒤 적용하세요.")
    # rect is in visible-frame coordinates; SetWindowPos takes the outer rect including the shadow.
    left, top, right, bottom = _shadow_inset(hwnd)
    if not _set_window_pos(
        hwnd, None, rect.x - left, rect.y - top,
        rect.width + left + right, rect.height + top + bottom, int(MOVE_FLAGS)
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
    left, top, right, bottom = _shadow_inset(hwnd)
    if not _set_window_pos(
        hwnd, None, 0, 0, rect.width + left + right, rect.height + top + bottom, int(lock_flags)
    ):
        raise _last_error()


_get_foreground = _bind(user32, "GetForegroundWindow", [], wt.HWND)
_set_foreground = _bind(user32, "SetForegroundWindow", [wt.HWND], wt.BOOL)
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
    ctypes.set_last_error(0)
    if not _set_window_pos(hwnd, None, x, y, 0, 0, flags):
        raise _position_error(f"toolbar-move x={x} y={y}", hwnd)


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


def is_fullscreen(target: window_schema.WindowInfo, *, minimized: bool,
                  maximized: bool, visible: bool) -> bool:
    """Heuristic for borderless fullscreen; maximized windows stay distinct."""
    if minimized or maximized or not visible:
        return False
    style = _get_window_long(target.hwnd, window_enum.WindowLongIndex.STYLE)
    if style & (window_enum.WindowStyle.CAPTION | window_enum.WindowStyle.THICKFRAME):
        return False
    bounds = monitor_bounds(target.hwnd, work=False)
    rect = target.rect
    return all(abs(a - b) <= 1 for a, b in (
        (rect.x, bounds.x), (rect.y, bounds.y),
        (rect.x + rect.width, bounds.x + bounds.width),
        (rect.y + rect.height, bounds.y + bounds.height),
    ))
