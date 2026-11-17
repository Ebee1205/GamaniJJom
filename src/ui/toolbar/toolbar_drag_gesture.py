from dataclasses import replace

from PySide6.QtCore import QObject, QTimer

import src.models.toolbar_event_schema as tb_es
import src.models.toolbar_schema as tb_s
from src.models.toolbar_enum import ToolbarEdge

DRAG_POLL_INTERVAL_MS = 16
DEFAULT_ATTACHED_OFFSET_DIP = 48


class ToolbarDragGesture(QObject):
    """Owns one toolbar drag: session, frame timer, snap preview and drop.

    Talks to the controller only through its public surface (`state`, `snapshot`,
    `dispatch`, `render`, `update`, `notification`, `tracking`, `windows`, `window`, `hwnd`).
    """

    def __init__(self, controller):
        super().__init__(controller)
        self._host = controller
        self._session = None
        self._timer = QTimer(self)
        self._timer.setInterval(DRAG_POLL_INTERVAL_MS)
        self._timer.timeout.connect(self.poll)

    @property
    def active(self):
        return self._session is not None

    # ------------------------------------------------------------ lifecycle

    def start(self):
        host = self._host
        if self.active or host.disposed:
            return
        try:
            rect = host.tracking.toolbar_rect(host.hwnd)
            self._session = tb_s.DragSession(
                host.tracking.cursor(), rect, host.tracking.monitor(rect).scale
            )
            self._timer.start()
        except OSError as error:
            self.end()
            host.notification.emit(str(error))
        host.render()

    def poll(self):
        if not self.active:
            return
        host = self._host
        try:
            if host.tracking.drag_cancelled():
                self.cancel()
                return
            raw, dx, dy = self._raw_rect()
            position = host.tracking.screen_position(raw)
            if host.state.attached and host.snapshot is not None:
                host.dispatch(self._attached_event(raw, position, dx, dy))
            else:
                host.dispatch(tb_es.FreeMoved(position))
            if not host.state.attached:
                host.tracking.place_raw(host.hwnd, raw)
            self._update_snap_preview(raw)
            host.render()
        except (OSError, ValueError) as error:
            self.end()
            host.notification.emit(str(error))
            host.render()

    def finish(self):
        if not self.active:
            return
        host = self._host
        try:
            self.poll()
            if not self.active:
                return
            rect = host.tracking.toolbar_rect(host.hwnd)
            position = host.tracking.screen_position(rect)
            disabled = host.tracking.snap_disabled()
            candidate, info = self._drop_candidate(rect, disabled)
            host.dispatch(tb_es.ToolbarDropped(position, candidate, disabled), target_info=info)
        except (OSError, ValueError) as error:
            host.notification.emit(str(error))
        finally:
            self.end()
            host.update()

    def cancel(self):
        if self.active:
            # Cancellation suppresses snap; already confirmed 48-DIP detach stays.
            self.end()
            self._host.update()

    def end(self):
        """Tear down the gesture without touching toolbar state. Idempotent."""
        self._session = None
        self._timer.stop()
        self._host.window.toolbar.handle.cancel_drag()
        self._host.window.show_candidate(None)

    # -------------------------------------------------------------- helpers

    def _raw_rect(self):
        """Toolbar rect following the cursor, plus the cursor delta since drag start."""
        session = self._session
        x, y = self._host.tracking.cursor()
        dx, dy = x - session.cursor_start[0], y - session.cursor_start[1]
        start = session.toolbar_start
        return replace(start, x=start.x + dx, y=start.y + dy), dx, dy

    def _attached_event(self, raw, position, dx, dy):
        host = self._host
        snapshot = host.snapshot
        maximized = snapshot.maximized
        placement = host.state.maximized_placement if maximized else host.state.normal_placement
        placement = placement or tb_s.AttachedPlacement(
            ToolbarEdge.RIGHT, DEFAULT_ATTACHED_OFFSET_DIP
        )

        target_rect = snapshot.target.rect
        scale = host.tracking.monitor(target_rect).scale
        horizontal = placement.edge in (ToolbarEdge.TOP, ToolbarEdge.BOTTOM)
        offset = (raw.x - target_rect.x if horizontal else raw.y - target_rect.y) / scale
        distance = (dy if horizontal else dx) / self._session.scale_start
        return tb_es.AttachedDragged(
            host.state.target, distance, position,
            replace(placement, offset_dip=offset), maximized,
        )

    def _update_snap_preview(self, raw):
        host = self._host
        info = None
        if not host.state.attached and not host.tracking.snap_disabled():
            _, info = host.tracking.nearest_candidate(raw)
        if info is None:
            host.window.show_candidate(None)
            return
        handle = host.window.show_candidate(info.rect)
        host.tracking.place_candidate(handle, info.rect)

    def _drop_candidate(self, rect, snap_disabled):
        host = self._host
        if host.state.attached or snap_disabled:
            return None, None
        candidate, info = host.tracking.nearest_candidate(rect)
        if info is not None:
            # Revalidate the candidate immediately before replacing a connection.
            info = host.windows.read(info)
            candidate = host.tracking.confirm_candidate(info, rect)
        return candidate, info

