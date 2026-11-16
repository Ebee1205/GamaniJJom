"""Native toolbar tracking/placement and pointer picking, independent of Qt."""
import os
import time
from dataclasses import dataclass

from src.adapters.windows import window_api
from src.models.window_schema import WindowInfo, WindowRect


@dataclass(frozen=True)
class ToolbarState:
    target: WindowInfo
    visible: bool
    minimized: bool
    active: bool
    fullscreen: bool

    @property
    def show_toolbar(self):
        return self.visible and self.active and not self.minimized and not self.fullscreen


class PickCancelled(Exception):
    pass


class ToolbarService:
    def __init__(self):
        self._deadline = None
        self._mouse_was_down = True

    def inspect(self, target: WindowInfo, *, interaction_handles=()) -> ToolbarState:
        current = window_api.read_window(target.hwnd)
        if current.identity != target.identity:
            raise OSError("대상 창의 프로세스가 변경되었습니다.")
        visible = window_api.is_visible(current.hwnd)
        minimized = window_api.is_minimized(current.hwnd)
        fullscreen = (not minimized and visible
                      and current.rect == window_api.monitor_bounds(current.hwnd, work=False))
        foreground = window_api.foreground_window()
        active = foreground == current.hwnd or foreground in interaction_handles
        return ToolbarState(current, visible, minimized, active, fullscreen)

    @staticmethod
    def placement(target: WindowRect, toolbar: WindowRect, area: WindowRect, offset):
        x = target.x + target.width - toolbar.width + offset[0]
        y = target.y - toolbar.height + offset[1]
        x = max(area.x, min(x, area.x + area.width - toolbar.width))
        y = max(area.y, min(y, area.y + area.height - toolbar.height))
        return x, y

    def place(self, toolbar_handle: int, target: WindowInfo, offset):
        native = window_api.read_window(toolbar_handle).rect
        area = window_api.monitor_bounds(target.hwnd)
        x, y = self.placement(target.rect, native, area, offset)
        if (native.x, native.y) != (x, y):
            window_api.place_toolbar(toolbar_handle, x, y)

    @property
    def is_picking(self):
        return self._deadline is not None

    def start_pick(self):
        self._deadline = time.monotonic() + 20
        self._mouse_was_down = True

    def cancel_pick(self):
        self._deadline = None

    def poll_pick(self):
        if not self.is_picking:
            return None
        if window_api.key_down(0x1B) or time.monotonic() >= self._deadline:
            self.cancel_pick()
            raise PickCancelled("대상 선택을 취소했습니다.")
        down = window_api.key_down(0x01)
        clicked = down and not self._mouse_was_down
        self._mouse_was_down = down
        if not clicked:
            return None
        target = window_api.read_window(window_api.window_at_cursor())
        if target.pid == os.getpid():
            return None  # Keep the list fallback and cancel controls usable.
        if not target.title.strip() or not window_api.is_regular_window(target.hwnd):
            raise ValueError("연결할 프로그램의 일반 창을 선택하세요.")
        self.cancel_pick()
        return target
