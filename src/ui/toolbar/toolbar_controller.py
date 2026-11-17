"""One toolbar: dispatch policy events, apply lock effects and render intent."""
from PySide6.QtCore import QObject, QTimer, Qt, Signal

from src.adapters.windows.window_event_watcher import WindowEventWatcher
import src.models.toolbar_event_schema as tb_es
import src.models.toolbar_schema as tb_s
from src.models.attachment import Attachment
from src.models.window_enum import WindowEvent
from src.models.window_schema import WindowClosedError
from src.services.toolbar_state_service import reduce_toolbar
from src.ui.toolbar.toolbar_drag_gesture import ToolbarDragGesture

EVENT_COALESCE_INTERVAL_MS = 16
NO_TARGET_MESSAGE = "연결된 대상 창이 없습니다."


class _ErrorGate:
    """Lets the same error message through only once until `clear()` is called."""

    def __init__(self):
        self._last = None

    @property
    def last(self):
        return self._last

    def is_new(self, error):
        message = str(error)
        if message == self._last:
            return False
        self._last = message
        return True

    def clear(self):
        self._last = None


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

    # ------------------------------------------------------------------ setup

    def __init__(self, window, attachment, lock_service, capture_service, toolbar_service, window_service, parent=None):
        super().__init__(parent)
        self.log = parent.ctx.log if parent is not None else None
        self.registry = parent.attachments if parent is not None else None
        self.window, self.attachment = window, attachment
        self.locks, self.capture_service = lock_service, capture_service
        self.tracking, self.windows = toolbar_service, window_service
        self.state = tb_s.ToolbarState(target=attachment.target.reference if attachment else None)

        self._snapshot = None
        self._last_presented = None
        self._presentation_visible = None
        self._startup_initialized = False
        self._disposed = False
        self._watch_attempted = False
        self._inspection_errors = _ErrorGate()
        self._placement_errors = _ErrorGate()

        self.drag = ToolbarDragGesture(self)
        self._watcher = WindowEventWatcher(self.window_event_received.emit)
        self._event_timer = QTimer(self)
        self._event_timer.setSingleShot(True)
        self._event_timer.setInterval(EVENT_COALESCE_INTERVAL_MS)
        self._event_timer.timeout.connect(self.update)
        self.window_event_received.connect(self.on_window_event, Qt.ConnectionType.QueuedConnection)

        self._connect_toolbar_signals()
        self.sync()

    def _connect_toolbar_signals(self):
        window = self.window
        toolbar = window.toolbar
        window.log = toolbar.log = toolbar.handle.log = self.log

        toolbar.pin_button.clicked.connect(self.detach_toolbar)
        toolbar.capture_options_requested.connect(
            lambda: self.notification.emit("캡처 옵션은 준비 중입니다."))
        for signal, slot in (
            (toolbar.lock_requested, self.toggle_lock),
            (toolbar.capture_requested, self.capture),
            (toolbar.position_requested, self.request_position),
            (toolbar.settings_requested, self.settings_requested.emit),
            (toolbar.attach_requested, self.attach_requested.emit),
            (toolbar.detach_requested, self.detach_toolbar),
            (toolbar.hide_requested, self.reveal),
            (toolbar.reset_requested, self.reset_position),
            (toolbar.quit_requested, self.quit_requested.emit),
            (toolbar.drag_started, self.drag.start),
            (toolbar.drag_moved, self.drag.poll),
            (toolbar.drag_finished, self.drag.finish),
            (toolbar.drag_cancelled, self.drag.cancel),
        ):
            signal.connect(slot)

    # ---------------------------------------------------------------- helpers

    @property
    def hwnd(self):
        return int(self.window.winId())

    @property
    def snapshot(self):
        return self._snapshot

    @property
    def disposed(self):
        return self._disposed

    @property
    def dragging(self):
        return self.drag.active

    def cancel_drag(self):
        self.drag.cancel()

    def _debug(self, category, message):
        if self.log is not None:
            self.log.debug(category, message)

    def _require_attachment(self):
        if self.attachment is None:
            self.notification.emit(NO_TARGET_MESSAGE)
            return False
        return True

    # ------------------------------------------------------- policy dispatch

    def dispatch(self, event, *, target_info=None):
        transition = reduce_toolbar(self.state, event)
        old_target = self.state.target
        new_target = transition.state.target
        if new_target != old_target:
            self._validate_new_connection(new_target, target_info)

        self._release_effect_locks(transition.effects)
        self.state = transition.state
        if self.state.target != old_target:
            self._switch_target(target_info)
        self.sync()
        return transition

    @staticmethod
    def _validate_new_connection(new_target, target_info):
        if new_target is None:
            return
        if target_info is None or target_info.reference != new_target:
            raise ValueError("A validated window is required for a new connection.")

    def _release_effect_locks(self, effects):
        if self.attachment is None:
            return
        for effect in effects:
            if self.attachment.target.reference == effect.target:
                self.locks.release(self.attachment)

    def _switch_target(self, target_info):
        if self.dragging:
            self.drag.end()
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

    # ------------------------------------------------------ public commands

    def select_target(self, target):
        current = self.windows.read(target)
        if self.dragging:
            self.cancel_drag()
        self.dispatch(tb_es.TargetSelected(current.reference), target_info=current)
        if self.attachment is not None:
            self.attachment.target = current
        self.update()

    def current_position(self):
        rect = self._last_presented or self.tracking.toolbar_rect(self.hwnd)
        return self.tracking.screen_position(rect)

    def detach_toolbar(self):
        if self.state.attached:
            self.dispatch(tb_es.DetachClicked(self.current_position()))
        self.update()

    def request_position(self):
        if self._require_attachment():
            self.position_requested.emit(self.attachment.target)

    def toggle_lock(self):
        if not self._require_attachment():
            self.sync()
            return
        try:
            self.locks.toggle(self.attachment)
        except (ValueError, OSError) as error:
            self.notification.emit(str(error))
        self.sync()
        self.changed.emit()

    def capture(self):
        if not self._require_attachment():
            return
        try:
            target = self.windows.read(self.attachment.target)
            saved_path = self.capture_service.capture(target)
            self.capture_completed.emit(f"캡처 저장 완료: {saved_path}")
        except (NotImplementedError, ValueError, OSError) as error:
            self.notification.emit(str(error))

    def sync(self):
        toolbar = self.window.toolbar
        attached = self.state.attached
        toolbar.pin_button.blockSignals(True)
        toolbar.pin_button.setChecked(attached)
        toolbar.pin_button.blockSignals(False)
        toolbar.pin_button.setToolTip(
            "점착 중 · 클릭하여 떼기" if attached else "비점착 · 창 가장자리에 드롭하여 점착")
        toolbar.handle.setEnabled(True)
        toolbar.set_locked(self.attachment is not None and self.attachment.locked_rect is not None)
        toolbar.lock_button.setEnabled(self.state.connected)

    def reveal(self):
        self.update()

    # Kept as an alias: external callers may still use `controller.hide()`.
    hide = reveal

    def reset_position(self):
        # Reset layout preferences without changing connection or attachment.
        self.dispatch(tb_es.PlacementReset())
        self.update()

    # ------------------------------------------------------ startup/recovery

    def initialize_startup(self, anchor_handle=None):
        """Initialize a fresh toolbar once; reopening the picker never resets it."""
        if self._startup_initialized or self.state.connected:
            self.reveal()
            return
        position = self.tracking.startup_position(self.hwnd, anchor_handle)
        self.state = tb_s.ToolbarState(free_position=position)
        self._startup_initialized = True
        self._snapshot = None
        self.sync()
        self.render()
        self._debug("TOOLBAR", f"Startup initialized mode=free connected=False "
                               f"monitor={position.monitor_id} x_dip={position.x_dip} y_dip={position.y_dip}")

    def recover_toolbar(self):
        """Explicitly retrieve the toolbar without restoring or unlocking its target."""
        try:
            if self.dragging:
                self.cancel_drag()
            if self.state.attached:
                self.dispatch(tb_es.DetachClicked(self.current_position()))
            position = self.tracking.recovery_position(self.hwnd)
            self.dispatch(tb_es.FreeMoved(position))
            self.update()
            self._debug("TOOLBAR", f"Toolbar recovered monitor={position.monitor_id} "
                                   f"x_dip={position.x_dip} y_dip={position.y_dip}")
            self.notification.emit("툴바를 현재 화면 위쪽 중앙에 표시했습니다. 연결과 잠금은 유지합니다.")
        except (OSError, ValueError) as error:
            self.notification.emit(str(error))

    # ---------------------------------------------------- target observation

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
            self._ensure_watching(reference)
            if not self._refresh_snapshot(reference):
                self.render()
                return
        self.sync()
        self.render()

    def _ensure_watching(self, reference):
        if self._watch_attempted and self._watcher.target == reference:
            return
        self._watch_attempted = True
        try:
            self._watcher.watch(reference)
        except OSError as error:
            self._watcher.target = reference
            self.notification.emit(f"창 상태 감지를 시작하지 못했습니다: {error}")

    def _refresh_snapshot(self, reference):
        """Inspect the target and apply the result. Returns False on a transient failure."""
        try:
            snapshot = self.tracking.inspect(self.attachment.target)
        except WindowClosedError:
            previous = self.attachment.target.identity
            self.dispatch(tb_es.TargetClosed(reference, self.current_position()))
            self.detach_requested.emit(previous)
            return True
        except OSError as error:
            if self._inspection_errors.is_new(error):
                self.notification.emit(f"창 정보를 확인하지 못했습니다. 연결을 유지합니다: {error}")
            # During a gesture, a transient query failure must not drop topmost.
            return False

        self._inspection_errors.clear()
        title_changed = self.attachment.target.title != snapshot.target.title
        self.attachment.target = snapshot.target
        self._snapshot = snapshot
        self.dispatch(tb_es.TargetStateObserved(snapshot))
        if snapshot.visible:
            self._enforce_lock(snapshot)
        if title_changed:
            self.window.setWindowTitle(f"GamaniJJom · {snapshot.target.title}")
            self.changed.emit()
        return True

    def _enforce_lock(self, snapshot):
        try:
            self.locks.enforce(self.attachment, snapshot.target)
        except (ValueError, OSError) as error:
            self.locks.release(self.attachment)
            self.notification.emit(f"Window Lock 해제: {error}")
            self.changed.emit()

    # ------------------------------------------------------------- rendering

    def render(self):
        if self._disposed:
            return
        snapshot = self._snapshot
        if self._should_show(snapshot):
            self._present(snapshot)
        else:
            self._hide(snapshot)

    def _should_show(self, snapshot):
        return (self.dragging or not self.state.attached
                or (snapshot is not None and snapshot.show_toolbar and not snapshot.fullscreen))

    def _hide(self, snapshot):
        if self._presentation_visible is not False:
            self._debug("TOOLBAR", f"Toolbar hidden mode={self.state.mode.value} "
                                   f"minimized={snapshot.minimized if snapshot else None} "
                                   f"fullscreen={snapshot.fullscreen if snapshot else None}")
        self._presentation_visible = False
        self.window.toolbar.menu.hide()
        self.window.hide()

    def _present(self, snapshot):
        self.window.ensure_visible()
        try:
            rect = self.tracking.render(self.hwnd, self.state, snapshot, dragging=self.dragging)
            self._last_presented = rect
            if self._presentation_visible is not True:
                self._debug("TOOLBAR", f"Toolbar shown hwnd={self.hwnd:#x} "
                                       f"mode={self.state.mode.value} x={rect.x} y={rect.y} "
                                       f"width={rect.width} height={rect.height}")
            self._presentation_visible = True
            if not self.state.attached and self.state.free_position is None:
                self.dispatch(tb_es.FreeMoved(self.tracking.screen_position(rect)))
            self._placement_errors.clear()
        except OSError as error:
            if self._placement_errors.is_new(error):
                self._debug("TOOLBAR", f"Toolbar placement failed: {error}")
                self.notification.emit(f"툴바를 배치하지 못했습니다: {error}")

    # -------------------------------------------------------------- teardown

    def dispose(self):
        self._disposed = True
        self._event_timer.stop()
        self.drag.end()
        self._watcher.close()
        if self._watcher.error is not None:
            self._debug("WINDOW", f"Window event cleanup error: {self._watcher.error}")
        if self.attachment is not None:
            self.locks.release(self.attachment)
        self.window.dispose()
        self.deleteLater()