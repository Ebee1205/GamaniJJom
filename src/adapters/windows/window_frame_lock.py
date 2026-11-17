"""Block native frame presses and observe external window geometry changes."""
import ctypes
from ctypes import wintypes as wt

from src.adapters.windows import window_api as api

WH_MOUSE_LL = 14
WM_LBUTTONDOWN = 0x0201
WM_NCHITTEST = 0x0084
HTCAPTION = 2
HTLEFT, HTBOTTOMRIGHT = 10, 17
GA_ROOT = 2
SMTO_ABORTIFHUNG = 2
EVENT_SYSTEM_MOVESIZESTART = 0x000A
EVENT_OBJECT_LOCATIONCHANGE = 0x800B

HookProc = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wt.WPARAM, wt.LPARAM)
WinEventProc = ctypes.WINFUNCTYPE(None, wt.HANDLE, wt.DWORD, wt.HWND, wt.LONG,
                                 wt.LONG, wt.DWORD, wt.DWORD)
install = api._bind(api.user32, "SetWindowsHookExW",
                    [ctypes.c_int, HookProc, wt.HINSTANCE, wt.DWORD], wt.HANDLE)
remove = api._bind(api.user32, "UnhookWindowsHookEx", [wt.HANDLE], wt.BOOL)
forward = api._bind(api.user32, "CallNextHookEx",
                    [wt.HANDLE, ctypes.c_int, wt.WPARAM, wt.LPARAM], ctypes.c_ssize_t)
hit_test = api._bind(api.user32, "SendMessageTimeoutW",
                     [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM, wt.UINT, wt.UINT,
                      ctypes.POINTER(ctypes.c_size_t)], ctypes.c_ssize_t)
module_handle = api._bind(ctypes.WinDLL("kernel32"), "GetModuleHandleW",
                          [wt.LPCWSTR], wt.HMODULE)
install_event = api._bind(api.user32, "SetWinEventHook",
                          [wt.DWORD, wt.DWORD, wt.HMODULE, WinEventProc,
                           wt.DWORD, wt.DWORD, wt.DWORD], wt.HANDLE)
remove_event = api._bind(api.user32, "UnhookWinEvent", [wt.HANDLE], wt.BOOL)


class WindowFrameLock:
    def __init__(self, on_change):
        self.targets = {}
        self.handle = None
        self.callback = HookProc(self._dispatch)
        self.event_callback = WinEventProc(self._dispatch_event)
        self.event_handles = []
        self.on_change = on_change
        self.errors = {}
        self.processing = set()

    def add(self, attachment):
        if self.handle is None:
            self.handle = install(WH_MOUSE_LL, self.callback, module_handle(None), 0)
            if not self.handle:
                self.handle = None
                raise api._last_error()
            for event in (EVENT_SYSTEM_MOVESIZESTART, EVENT_OBJECT_LOCATIONCHANGE):
                handle = install_event(event, event, None, self.event_callback, 0, 0, 0)
                if not handle:
                    error = api._last_error()
                    self._uninstall()
                    raise error
                self.event_handles.append(handle)
        self.targets[attachment.target.hwnd] = attachment

    def discard(self, attachment):
        hwnd = attachment.target.hwnd
        if self.targets.get(hwnd) is attachment:
            del self.targets[hwnd]
            self.errors.pop(hwnd, None)
        if not self.targets:
            self._uninstall()

    def _uninstall(self):
        while self.event_handles:
            if not remove_event(self.event_handles[-1]):
                raise api._last_error()
            self.event_handles.pop()
        if self.handle:
            if not remove(self.handle):
                raise api._last_error()
            self.handle = None

    def check_error(self, attachment):
        error = self.errors.pop(attachment.target.hwnd, None)
        if error is not None:
            raise error

    def _dispatch_event(self, _hook, event, hwnd, object_id, child_id, _thread, _time):
        attachment = self.targets.get(hwnd)
        if (attachment is None or attachment.locked_rect is None or hwnd in self.processing
                or object_id != 0 or child_id != 0 or hwnd in self.errors):
            return
        pid = wt.DWORD()
        if not api._get_process_id(hwnd, ctypes.byref(pid)) or pid.value != attachment.target.pid:
            return
        self.processing.add(hwnd)
        try:
            self.on_change(attachment)
        except (OSError, ValueError) as error:
            self.errors[hwnd] = error
        finally:
            self.processing.remove(hwnd)

    def _dispatch(self, code, message, data):
        if code == 0 and message == WM_LBUTTONDOWN:
            # POINT is the first member of MSLLHOOKSTRUCT.
            point = ctypes.cast(data, ctypes.POINTER(wt.POINT)).contents
            if self._blocks(point):
                return 1
        return forward(None, code, message, data)

    def _blocks(self, point):
        leaf = api._window_from_point(point)
        root = api._get_ancestor(leaf, GA_ROOT)
        attachment = self.targets.get(root)
        if attachment is None or attachment.locked_rect is None:
            return False
        pid = wt.DWORD()
        api._get_process_id(root, ctypes.byref(pid))
        if pid.value != attachment.target.pid or api.is_maximized(root):
            return False
        coords = (point.x & 0xffff) | ((point.y & 0xffff) << 16)
        result = ctypes.c_size_t()
        if not hit_test(root, WM_NCHITTEST, 0, coords, SMTO_ABORTIFHUNG, 20,
                        ctypes.byref(result)):
            return False
        return result.value == HTCAPTION or HTLEFT <= result.value <= HTBOTTOMRIGHT
