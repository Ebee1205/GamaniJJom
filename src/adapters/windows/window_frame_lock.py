"""Block native caption and sizing presses before the target receives them."""
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

HookProc = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wt.WPARAM, wt.LPARAM)
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


class WindowFrameLock:
    def __init__(self):
        self.targets = {}
        self.handle = None
        self.callback = HookProc(self._dispatch)

    def add(self, attachment):
        if self.handle is None:
            self.handle = install(WH_MOUSE_LL, self.callback, module_handle(None), 0)
            if not self.handle:
                self.handle = None
                raise api._last_error()
        self.targets[attachment.target.hwnd] = attachment

    def discard(self, attachment):
        hwnd = attachment.target.hwnd
        if self.targets.get(hwnd) is attachment:
            del self.targets[hwnd]
        if self.handle and not self.targets and remove(self.handle):
            self.handle = None

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
