"""One toolbar: dispatch policy events, apply lock effects and render intent."""
from dataclasses import replace

from PySide6.QtCore import QObject, QTimer, Qt, Signal

from src.adapters.windows.window_event_watcher import WindowEventWatcher
from src.models.attachment import Attachment
from src.models.toolbar_enum import ToolbarEdge
from src.models.toolbar_event_schema import (
    AttachedDragged, DetachClicked, FreeMoved, PlacementReset, TargetClosed, TargetSelected,
    TargetStateObserved, ToolbarDropped,
)
from src.models.toolbar_schema import AttachedPlacement, DragSession, ToolbarState
from src.models.window_enum import WindowEvent
from src.models.window_schema import WindowClosedError, WindowRect
from src.services.toolbar_state_service import reduce_toolbar


class ToolbarController(QObject):
    window_event_received = Signal(object)
    position_requested = Signal(object)
    settings_requested = Signal()
    attach_requested = Signal()
    detach_requested = Signal(object)
    notification = Signal(str)
    capture_completed = Signal(str)
    connection_changed = Signal()
    changed = Signal()
    quit_requested = Signal()

    def __init__(self, window, attachment, lock_service, capture_service, toolbar_service, window_service, parent=None):
        super().__init__(parent)
        self.log = parent.ctx.log if parent is not None else None
        self.registry = parent.attachments if parent is not None else None
        self.window, self.attachment = window, attachment
        self.locks, self.capture_service = lock_service, capture_service
        self.tracking, self.windows = toolbar_service, window_service
        self.state = ToolbarState(target=attachment.target.reference if attachment else None)
        self._snapshot = None
        self._drag = None
        self._last_presented = None
        self._inspection_error = self._placement_error = None
        self._disposed = self._watch_attempted = False
        self._watcher = WindowEventWatcher(self.window_event_received.emit)
        self._event_timer = QTimer(self)
        self._event_timer.setSingleShot(True)
        self._event_timer.setInterval(16)
        self._event_timer.timeout.connect(self.update)
        self._drag_timer = QTimer(self)
        self._drag_timer.setInterval(16)
        self._drag_timer.timeout.connect(self.poll_drag)
        self.window_event_received.connect(self.on_window_event, Qt.ConnectionType.QueuedConnection)
        window.log = self.log
        toolbar = window.toolbar
        toolbar.log = self.log
        toolbar.handle.log = self.log
        toolbar.pin_button.clicked.connect(self.detach_toolbar)
        toolbar.lock_requested.connect(self.toggle_lock)
        toolbar.capture_requested.connect(self.capture)
        toolbar.position_requested.connect(self.request_position)
        toolbar.capture_options_requested.connect(lambda: self.notification.emit("캡처 옵션은 준비 중입니다."))
        toolbar.settings_requested.connect(self.settings_requested.emit)
        toolbar.attach_requested.connect(self.attach_requested.emit)
        toolbar.detach_requested.connect(self.detach_toolbar)
        toolbar.hide_requested.connect(self.reveal)
        toolbar.reset_requested.connect(self.reset_position)
        toolbar.quit_requested.connect(self.quit_requested.emit)
        toolbar.drag_started.connect(self.start_drag)
        toolbar.drag_moved.connect(self.poll_drag)
        toolbar.drag_finished.connect(self.finish_drag)
        toolbar.drag_cancelled.connect(self.cancel_drag)
        self.sync()

    @property
    def dragging(self):
        return self._drag is not None

    def dispatch(self, event, *, target_info=None):
        transition = reduce_toolbar(self.state, event)
        old_target = self.state.target
        if transition.state.target != old_target and transition.state.target is not None:
            if target_info is None or target_info.reference != transition.state.target:
                raise ValueError("A validated window is required for a new connection.")
        for effect in transition.effects:
            if self.attachment is not None and self.attachment.target.reference == effect.target:
                self.locks.release(self.attachment)
        self.state = transition.state
        if self.state.target != old_target:
            if self.dragging:
                self._end_gesture()
            self._watcher.close()
            self._watch_attempted = False
            self._snapshot = None
            self.attachment = Attachment(target_info) if target_info is not None else None
            if self.registry is not None:
                self.registry.attachments.clear()
                if self.attachment is not None:
                    self.registry.attachments[self.attachment.target.identity] = self.attachment
            self.connection_changed.emit()
            self.changed.emit()
        self.sync()
        return transition

    def select_target(self, target):
        current = self.windows.read(target)
        if self.dragging:
            self.cancel_drag()
        self.dispatch(TargetSelected(current.reference), target_info=current)
        if self.attachment is not None:
            self.attachment.target = current
        self.update()

    def current_position(self):
        rect = self._last_presented or self.tracking.toolbar_rect(int(self.window.winId()))
        return self.tracking.screen_position(rect)

    def detach_toolbar(self):
        if self.state.attached:
            self.dispatch(DetachClicked(self.current_position()))
        self.update()

    def request_position(self):
        if self.attachment is None:
            self.notification.emit("연결된 대상 창이 없습니다.")
        else:
            self.position_requested.emit(self.attachment.target)

    def toggle_lock(self):
        if self.attachment is None:
            self.notification.emit("연결된 대상 창이 없습니다.")
            self.sync()
            return
        try:
            self.locks.toggle(self.attachment)
        except (ValueError, OSError) as error:
            self.notification.emit(str(error))
        self.sync()
        self.changed.emit()

    def capture(self):
        if self.attachment is None:
            self.notification.emit("연결된 대상 창이 없습니다.")
            return
        try:
            target = self.windows.read(self.attachment.target)
            saved_path = self.capture_service.capture(target)
            self.capture_completed.emit(f"캡처 저장 완료: {saved_path}")
        except (NotImplementedError, ValueError, OSError) as error:
            self.notification.emit(str(error))

    def sync(self):
        toolbar = self.window.toolbar
        toolbar.pin_button.blockSignals(True)
        toolbar.pin_button.setChecked(self.state.attached)
        toolbar.pin_button.blockSignals(False)
        toolbar.pin_button.setToolTip("점착 중 · 클릭하여 떼기" if self.state.attached else "비점착 · 창 가장자리에 드롭하여 점착")
        toolbar.handle.setEnabled(True)
        toolbar.set_locked(self.attachment is not None and self.attachment.locked_rect is not None)
        toolbar.lock_button.setEnabled(self.state.connected)

    def reveal(self):
        self.update()

    hide = reveal

    def reset_position(self):
        # Reset layout preferences without changing connection or attachment.
        self.dispatch(PlacementReset())
        self.update()

    def start_drag(self):
        if self.dragging or self._disposed:
            return
        try:
            rect = self.tracking.toolbar_rect(int(self.window.winId()))
            self._drag = DragSession(self.tracking.cursor(), rect, self.tracking.monitor(rect).scale)
            self._drag_timer.start()
            self.render()
        except OSError as error:
            self._end_gesture()
            self.notification.emit(str(error))
            self.render()

    def poll_drag(self):
        if not self.dragging:
            return
        try:
            if self.tracking.drag_cancelled():
                self.cancel_drag()
                return
            session = self._drag
            x, y = self.tracking.cursor()
            dx, dy = x - session.cursor_start[0], y - session.cursor_start[1]
            raw = replace(session.toolbar_start, x=session.toolbar_start.x + dx,
                          y=session.toolbar_start.y + dy)
            position = self.tracking.screen_position(raw)
            if self.state.attached and self._snapshot is not None:
                maximized = self._snapshot.maximized
                placement = self.state.maximized_placement if maximized else self.state.normal_placement
                placement = placement or AttachedPlacement(ToolbarEdge.RIGHT, 48)
                target = self._snapshot.target.rect
                scale = self.tracking.monitor(target).scale
                horizontal = placement.edge in (ToolbarEdge.TOP, ToolbarEdge.BOTTOM)
                offset = (raw.x - target.x if horizontal else raw.y - target.y) / scale
                distance = (dy if horizontal else dx) / session.scale_start
                self.dispatch(AttachedDragged(self.state.target, distance, position,
                                             replace(placement, offset_dip=offset), maximized))
            else:
                self.dispatch(FreeMoved(position))
            if not self.state.attached:
                self.tracking.place_raw(int(self.window.winId()), raw)
            candidate, info = (None, None)
            if not self.state.attached and not self.tracking.snap_disabled():
                candidate, info = self.tracking.nearest_candidate(raw)
            if info is not None:
                handle = self.window.show_candidate(info.rect)
                self.tracking.place_candidate(handle, info.rect)
            else:
                self.window.show_candidate(None)
            self.render()
        except (OSError, ValueError) as error:
            self._end_gesture()
            self.notification.emit(str(error))
            self.render()

    def _end_gesture(self):
        self._drag = None
        self._drag_timer.stop()
        self.window.toolbar.handle.cancel_drag()
        self.window.show_candidate(None)

    def finish_drag(self):
        if not self.dragging:
            return
        try:
            self.poll_drag()
            if not self.dragging:
                return
            rect = self.tracking.toolbar_rect(int(self.window.winId()))
            position = self.tracking.screen_position(rect)
            disabled = self.tracking.snap_disabled()
            candidate, info = (None, None)
            if not self.state.attached and not disabled:
                candidate, info = self.tracking.nearest_candidate(rect)
                if info is not None:
                    # Revalidate the candidate immediately before replacing a connection.
                    info = self.windows.read(info)
                    candidate = self.tracking.confirm_candidate(info, rect)
            self.dispatch(ToolbarDropped(position, candidate, disabled), target_info=info)
        except (OSError, ValueError) as error:
            self.notification.emit(str(error))
        finally:
            self._end_gesture()
            self.update()

    def cancel_drag(self):
        if self.dragging:
            # Cancellation suppresses snap; already confirmed 48-DIP detach stays.
            self._end_gesture()
            self.update()

    def on_window_event(self, change):
        if (self._disposed or change.target != self.state.target
                or change.generation != self._watcher.generation):
            return
        if change.event == WindowEvent.DESTROY:
            self._event_timer.stop()
            self.update()
        elif not self._event_timer.isActive():
            self._event_timer.start()

    def update(self):
        if self._disposed:
            return
        if self.attachment is not None:
            reference = self.attachment.target.reference
            if not self._watch_attempted or self._watcher.target != reference:
                self._watch_attempted = True
                try:
                    self._watcher.watch(reference)
                except OSError as error:
                    self._watcher.target = reference
                    self.notification.emit(f"창 상태 감지를 시작하지 못했습니다: {error}")
            try:
                snapshot = self.tracking.inspect(self.attachment.target)
            except WindowClosedError:
                previous = self.attachment.target.identity
                self.dispatch(TargetClosed(reference, self.current_position()))
                self.detach_requested.emit(previous)
            except OSError as error:
                if str(error) != self._inspection_error:
                    self.notification.emit(f"창 정보를 확인하지 못했습니다. 연결을 유지합니다: {error}")
                    self._inspection_error = str(error)
                # During a gesture, a transient query failure must not drop topmost.
                self.render()
                return
            else:
                self._inspection_error = None
                title_changed = self.attachment.target.title != snapshot.target.title
                self.attachment.target = snapshot.target
                self._snapshot = snapshot
                self.dispatch(TargetStateObserved(snapshot))
                if snapshot.visible:
                    try:
                        self.locks.enforce(self.attachment, snapshot.target)
                    except (ValueError, OSError) as error:
                        self.locks.release(self.attachment)
                        self.notification.emit(f"Window Lock 해제: {error}")
                        self.changed.emit()
                if title_changed:
                    self.window.setWindowTitle(f"GamaniJJom · {snapshot.target.title}")
                    self.changed.emit()
        self.sync()
        self.render()

    def render(self):
        if self._disposed:
            return
        snapshot = self._snapshot
        visible = (self.dragging or not self.state.attached
                   or (snapshot is not None and snapshot.show_toolbar and not snapshot.fullscreen))
        if not visible:
            self.window.toolbar.menu.hide()
            self.window.hide()
            return
        self.window.show()
        try:
            rect = self.tracking.render(int(self.window.winId()), self.state, snapshot,
                                        dragging=self.dragging)
            self._last_presented = rect
            if not self.state.attached and self.state.free_position is None:
                self.dispatch(FreeMoved(self.tracking.screen_position(rect)))
            self._placement_error = None
        except OSError as error:
            if str(error) != self._placement_error:
                self.notification.emit(f"툴바를 배치하지 못했습니다: {error}")
                self._placement_error = str(error)

    def dispose(self):
        self._disposed = True
        self._event_timer.stop()
        self._end_gesture()
        self._watcher.close()
        if self._watcher.error is not None and self.log is not None:
            self.log.debug("WINDOW", f"Window event cleanup error: {self._watcher.error}")
        if self.attachment is not None:
            self.locks.release(self.attachment)
        self.window.dispose()
        self.deleteLater()
