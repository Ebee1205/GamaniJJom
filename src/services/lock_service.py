"""Enforce captured geometry by blocking move/size operations."""
import ctypes
from ctypes import wintypes

from src.adapters.windows import window_api
from src.adapters.windows.window_frame_lock import WindowFrameLock
from src.models.attachment import Attachment
from src.models.window_enum import GuiThreadFlag, WindowMessage
from src.models.window_schema import WindowInfo
from src.services.window_service import WindowService

user32 = ctypes.WinDLL("user32", use_last_error=True)

user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.c_void_p]
user32.GetGUIThreadInfo.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL



class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


class LockService:
    def __init__(self, windows: WindowService):
        self.windows = windows
        self.guard = WindowFrameLock(self._on_change)

    def release(self, attachment: Attachment) -> None:
        attachment.locked_rect = None
        self.guard.discard(attachment)

    def toggle(self, attachment: Attachment) -> bool:
        if attachment.locked_rect is not None:
            self.release(attachment)
            return False
        current = self.windows.read(attachment.target)
        if self.windows.is_suspended(current):
            raise ValueError("일반 창으로 복원한 뒤 Lock을 켜세요.")
        self.guard.add(attachment)
        attachment.locked_rect = current.rect
        return True

    @staticmethod
    def _is_moving(hwnd: int) -> bool:
        """대상 창이 현재 사용자 이동/리사이즈 모달 루프 중인지 확인."""
        info = GUITHREADINFO()
        info.cbSize = ctypes.sizeof(GUITHREADINFO)
        thread_id = user32.GetWindowThreadProcessId(hwnd, None)
        if not thread_id:
            raise ctypes.WinError(ctypes.get_last_error())
        if not user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        return bool(info.flags & GuiThreadFlag.INMOVESIZE) and info.hwndMoveSize == hwnd

    @staticmethod
    def _cancel_move(hwnd: int) -> None:
        """진행 중인 이동/리사이즈를 취소."""
        if not user32.PostMessageW(hwnd, WindowMessage.CANCELMODE, 0, 0):
            raise ctypes.WinError(ctypes.get_last_error())

    def _on_change(self, attachment: Attachment) -> None:
        if window_api.is_visible(attachment.target.hwnd):
            current = self.windows.read(attachment.target)
            self.enforce(attachment, current)

    def enforce(self, attachment: Attachment, current: WindowInfo) -> bool:
        """Block movement while locked. Returns True if an action was taken."""
        desired = attachment.locked_rect
        if desired is None:
            self.guard.discard(attachment)
            return False
        self.guard.check_error(attachment)
        if self.windows.is_suspended(current):
            return False

        moving = self._is_moving(current.hwnd)
        if moving:
            self._cancel_move(current.hwnd)
        if current.rect != desired:
            self.windows.apply(current, desired)
            return True
        return moving
