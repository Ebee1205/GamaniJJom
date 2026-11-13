"""Window operations shared by the UI and future multi-window locking policies."""
import os

from src.models.window_schema import WindowInfo, WindowRect
from src.platform.windows import window_api
from src.platform.windows.window_finder import find_windows


class WindowService:
    def list_windows(self) -> list[WindowInfo]:
        return find_windows(excluded_pid=os.getpid())

    def read(self, target: WindowInfo) -> WindowInfo:
        current = window_api.read_window(target.hwnd)
        if current.pid != target.pid:
            raise OSError("대상 창이 다른 프로세스로 바뀌었습니다. 다시 선택하세요.")
        if not window_api.is_regular_window(target.hwnd):
            raise OSError("대상 창을 사용할 수 없습니다. 목록을 새로고침하세요.")
        return current

    def apply(self, target: WindowInfo, rect: WindowRect) -> None:
        if not all(type(value) is int for value in (rect.x, rect.y, rect.width, rect.height)):
            raise ValueError("좌표와 크기는 정수로 입력하세요.")
        if not (-2147483648 <= rect.x <= 2147483647
                and -2147483648 <= rect.y <= 2147483647):
            raise ValueError("X/Y가 Windows 좌표 범위를 벗어났습니다.")
        if not (1 <= rect.width <= 2147483647 and 1 <= rect.height <= 2147483647):
            raise ValueError("너비와 높이는 1 이상의 정수로 입력하세요.")
        current = self.read(target)
        window_api.set_rect(current.hwnd, rect)
