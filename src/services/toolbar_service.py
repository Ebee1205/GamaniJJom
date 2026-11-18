"""Native toolbar tracking/placement and pointer picking, independent of Qt."""
import os
import time

from src.adapters.windows import window_api
from src.models.window_schema import WindowInfo, WindowRect, WindowState
from src.services.window_service import WindowService
from src.models.toolbar_schema import toolbar_is_topmost, TargetRelativePosition, AttachedPlacement
from src.models.toolbar_enum import ToolbarEdge
from src.models.toolbar_event_schema import SnapCandidate
from src.services.toolbar_layout_service import (
    attached_position, clamp_position, from_screen_position, snap_candidate, to_screen_position,
)


class PickCancelled(Exception):
    pass


class ToolbarService:
    def __init__(self, windows: WindowService | None = None):
        self.windows = windows if windows is not None else WindowService()
        self._deadline = None
        self._mouse_was_down = True
        self.relative_order_limited = False
        self.radial = False

    def inspect(self, target: WindowInfo, *, interaction_handles=()) -> WindowState:
        return self.windows.inspect(target, interaction_handles=interaction_handles)

    @staticmethod
    def toolbar_rect(handle):
        return window_api.read_window(handle).rect

    @staticmethod
    def cursor():
        return window_api.cursor_position()

    @staticmethod
    def monitor(rect):
        return window_api.monitor_at(rect.x, rect.y)

    def screen_position(self, rect):
        return to_screen_position(rect, self.monitor(rect))

    def free_anchor(self, position, target):
        monitors = window_api.available_monitors()
        monitor = next((m for m in monitors if m.device == position.monitor_id), monitors[0])
        x, y = from_screen_position(position, monitor)
        scale = self.monitor(target.rect).scale
        return TargetRelativePosition((x - target.rect.x) / scale, (y - target.rect.y) / scale)

    def pointed_candidate(self, target, toolbar, *, maximized=False):
        x, y = self.cursor()
        rect = target.rect
        scale = self.monitor(rect).scale
        edge = min(((abs(y - rect.y), ToolbarEdge.TOP),
                    (abs(x - rect.x - rect.width), ToolbarEdge.RIGHT),
                    (abs(y - rect.y - rect.height), ToolbarEdge.BOTTOM),
                    (abs(x - rect.x), ToolbarEdge.LEFT)), key=lambda item: item[0])[1]
        horizontal = edge in (ToolbarEdge.TOP, ToolbarEdge.BOTTOM)
        offset = ((x - rect.x - toolbar.width / 2) if horizontal
                  else (y - rect.y - toolbar.height / 2)) / scale
        length = ((rect.width - toolbar.width) if horizontal else (rect.height - toolbar.height)) / scale
        return SnapCandidate(target.reference, AttachedPlacement(edge, max(0, min(offset, length))),
                             0, maximized)

    def startup_position(self, handle, anchor_handle=None):
        """Place a free toolbar just above the picker's top-right corner.

        Use the monitor at that corner, including secondary/negative-coordinate
        displays. This is only an initial position, never an attachment target.
        """
        toolbar = self.toolbar_rect(handle)
        anchor = window_api.read_window(anchor_handle).rect if anchor_handle is not None else None
        monitor = (window_api.monitor_at(anchor.x + anchor.width - 1, anchor.y)
                   if anchor is not None else window_api.available_monitors()[0])
        area = monitor.work_area
        margin = round(12 * monitor.scale)
        if anchor is not None:
            x = anchor.x + anchor.width - toolbar.width
            y = anchor.y - toolbar.height - margin
            if y < area.y:
                # No room above the picker: avoid its caption buttons.
                y = anchor.y + round(48 * monitor.scale)
        else:
            x, y = area.x + area.width - toolbar.width - margin, area.y + margin
        x, y = clamp_position(x, y, toolbar, area)
        return to_screen_position(WindowRect(x, y, toolbar.width, toolbar.height), monitor)

    def recovery_position(self, handle):
        """An explicit recovery action places the toolbar on the cursor's monitor."""
        toolbar = self.toolbar_rect(handle)
        x, y = self.cursor()
        monitor = window_api.monitor_at(x, y)
        area = monitor.work_area
        x = area.x + (area.width - toolbar.width) // 2
        y = area.y + round(48 * monitor.scale)
        x, y = clamp_position(x, y, toolbar, area)
        return to_screen_position(WindowRect(x, y, toolbar.width, toolbar.height), monitor)

    @staticmethod
    def snap_disabled():
        return window_api.key_down(0x12)  # Alt; reevaluated at drop time.

    @staticmethod
    def drag_cancelled():
        return window_api.key_down(0x1B)

    @staticmethod
    def place_raw(handle, rect):
        window_api.place_toolbar(handle, rect.x, rect.y)

    @staticmethod
    def place_candidate(handle, rect):
        window_api.set_rect(handle, rect)

    def place_picker(self, handle, x, y):
        rect = self.toolbar_rect(handle)
        monitor = window_api.monitor_at(x, y)
        x, y = clamp_position(x, y, rect, monitor.work_area)
        window_api.place_toolbar(handle, x, y)

    def confirm_candidate(self, target, rect):
        if (not window_api.is_regular_window(target.hwnd)
                or window_api.is_minimized(target.hwnd)):
            return None
        return snap_candidate(target, rect, self.monitor(target.rect).scale,
                              maximized=window_api.is_maximized(target.hwnd))

    def nearest_candidate(self, rect):
        best, info = None, None
        # EnumWindows order preserves Z-order tie priority. Do not title-sort.
        for hwnd in window_api.enumerate_handles():
            try:
                if not window_api.is_regular_window(hwnd) or window_api.is_minimized(hwnd):
                    continue
                current = window_api.read_window(hwnd)
                if current.pid == os.getpid():
                    continue
                candidate = snap_candidate(current, rect, self.monitor(current.rect).scale,
                                           maximized=window_api.is_maximized(hwnd))
            except OSError:
                continue
            if candidate is not None and (best is None or candidate.distance_dip < best.distance_dip):
                best, info = candidate, current
        return best, info

    def render(self, handle, state, snapshot, *, dragging=False):
        toolbar = self.toolbar_rect(handle)
        if state.attached and snapshot is not None:
            monitor = self.monitor(snapshot.target.rect)
            placement = state.maximized_placement if snapshot.maximized else state.normal_placement
            x, y = attached_position(snapshot.target.rect, toolbar, placement, monitor.scale,
                                     maximized=snapshot.maximized)
            if self.radial and not snapshot.maximized:
                # HTML positions the circle's center directly on the target edge.
                edge = placement.edge.value if placement is not None else 'right'
                if edge == 'top':
                    y += toolbar.height // 2
                elif edge == 'bottom':
                    y -= toolbar.height // 2
                elif edge == 'left':
                    x += toolbar.width // 2
                else:
                    x -= toolbar.width // 2
        elif state.connected and state.free_anchor is not None and snapshot is not None:
            monitor = self.monitor(snapshot.target.rect)
            x = snapshot.target.rect.x + round(state.free_anchor.x_dip * monitor.scale)
            y = snapshot.target.rect.y + round(state.free_anchor.y_dip * monitor.scale)
            monitor = window_api.monitor_at(x + toolbar.width // 2, y + toolbar.height // 2)
        else:
            monitors = window_api.available_monitors()
            position = state.free_position
            monitor = next((m for m in monitors if position and m.device == position.monitor_id), monitors[0])
            if position and position.monitor_id == monitor.device:
                x, y = from_screen_position(position, monitor)
            else:
                margin = round(12 * monitor.scale)
                x, y = (monitor.work_area.x + monitor.work_area.width - toolbar.width - margin,
                        monitor.work_area.y + margin)
        if state.attached or not dragging:
            x, y = clamp_position(x, y, toolbar, monitor.work_area)
        if (x, y) != (toolbar.x, toolbar.y):
            window_api.place_toolbar(handle, x, y)
        ordered = window_api.set_toolbar_order(
            handle, topmost=toolbar_is_topmost(state, dragging=dragging),
            target=state.target.hwnd if state.attached else None,
        )
        self.relative_order_limited = not ordered
        return WindowRect(x, y, toolbar.width, toolbar.height)

    def bring_attached_pair(self, handle, target):
        current = self.windows.read(target)
        return window_api.bring_attached_pair(handle, current.hwnd)

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
