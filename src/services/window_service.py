"""Window operations shared by the UI and future multi-window locking policies."""
import os
from dataclasses import replace

from src.models.window_schema import WindowClosedError, WindowInfo, WindowRect, WindowState
from src.adapters.windows import window_api
from src.adapters.windows import window_finder

INT32_MIN = -(2 ** 31)
INT32_MAX = 2 ** 31 - 1


def _validate_rect(rect: WindowRect) -> None:
    """Reject values that a Win32 `int` parameter cannot represent."""
    # type() is int 비교로 bool(True/False)도 거부한다.
    if not all(type(value) is int for value in (rect.x, rect.y, rect.width, rect.height)):
        raise ValueError("좌표와 크기는 정수로 입력하세요.")
    if not all(INT32_MIN <= value <= INT32_MAX for value in (rect.x, rect.y)):
        raise ValueError("X/Y가 Windows 좌표 범위를 벗어났습니다.")
    if not all(1 <= value <= INT32_MAX for value in (rect.width, rect.height)):
        raise ValueError("너비와 높이는 1 이상의 정수로 입력하세요.")


class WindowService:
    def is_suspended(self, target: WindowInfo) -> bool:
        return window_api.is_minimized(target.hwnd) or window_api.is_maximized(target.hwnd)

    def list_windows(self) -> list[WindowInfo]:
        return window_finder.find_windows(excluded_pid=os.getpid())

    def read(self, target: WindowInfo) -> WindowInfo:
        current = window_api.read_window(target.hwnd)
        if current.identity != target.identity:
            raise WindowClosedError("Target window identity changed. Select the window again.")
        # Discovery eligibility (visible/listable) is not connection validity.
        # Hidden and cloaked windows remain valid connected targets.
        return current

    def inspect(self, target: WindowInfo, *, interaction_handles=()) -> WindowState:
        current = self.read(target)
        minimized = window_api.is_minimized(current.hwnd)
        maximized = window_api.is_maximized(current.hwnd)
        visible = window_api.is_visible(current.hwnd)
        # GetWindowRect may report minimized coordinates such as -32000.
        # Keep the last accepted rectangle; restoration reads actual bounds.
        if minimized:
            current = replace(current, rect=target.rect)
        fullscreen = window_api.is_fullscreen(
            current, minimized=minimized, maximized=maximized, visible=visible,
        )
        foreground = window_api.foreground_window()
        active = foreground == current.hwnd or foreground in interaction_handles
        return WindowState(current, visible, minimized, active, fullscreen, maximized)

    def apply(self, target: WindowInfo, rect: WindowRect) -> None:
        _validate_rect(rect)
        current = self.read(target)
        window_api.set_rect(current.hwnd, rect)

    def lock_size(self, target: WindowInfo, rect: WindowRect) -> None:
        """Lock window size only; prevent any movement."""
        _validate_rect(rect)
        current = self.read(target)
        window_api.lock_size(current.hwnd, rect)
