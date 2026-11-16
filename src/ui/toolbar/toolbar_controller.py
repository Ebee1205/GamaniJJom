"""Connect one toolbar view to attachment, lock, capture and tracking services."""
from PySide6.QtCore import QObject, Signal


class ToolbarController(QObject):
    position_requested = Signal(object)
    settings_requested = Signal()
    attach_requested = Signal()
    detach_requested = Signal(object)
    notification = Signal(str)
    capture_completed = Signal(str)
    changed = Signal()
    quit_requested = Signal()

    def __init__(self, window, attachment, lock_service, capture_service, toolbar_service, window_service, parent=None):
        super().__init__(parent)
        self.log = parent.ctx.log if parent is not None else None
        self.window = window
        self.attachment = attachment
        self.locks = lock_service
        self.capture_service = capture_service
        self.tracking = toolbar_service
        self.windows = window_service
        self._placement_error = None
        window.log = self.log
        toolbar = window.toolbar
        toolbar.log = self.log
        toolbar.handle.log = self.log
        toolbar.pin_button.log = self.log
        toolbar.pin_button.toggled.connect(self.set_pinned)
        toolbar.lock_button.log = self.log
        toolbar.capture_button.log = self.log
        toolbar.more_button.log = self.log
        toolbar.lock_requested.connect(self.toggle_lock)
        toolbar.capture_requested.connect(self.capture)
        toolbar.position_requested.connect(lambda: self.position_requested.emit(self.attachment.target))
        toolbar.capture_options_requested.connect(lambda: self.notification.emit("캡처 저장 옵션은 준비 중입니다."))
        toolbar.settings_requested.connect(self.settings_requested.emit)
        toolbar.attach_requested.connect(self.attach_requested.emit)
        toolbar.detach_requested.connect(lambda: self.detach_requested.emit(self.attachment.target.identity))
        toolbar.hide_requested.connect(self.hide)
        toolbar.reset_requested.connect(self.reset_position)
        toolbar.quit_requested.connect(self.quit_requested.emit)
        toolbar.dragged.connect(self.drag)

    def set_pinned(self, pinned: bool):
        self.window.set_pinned(pinned)
        self.window.toolbar.handle.setEnabled(not pinned)
        self.update()

    def toggle_lock(self):
        if self.log is not None:
            self.log.debug("TOOLBAR", f">> Lock toggle requested")
        try:
            self.locks.toggle(self.attachment)
            if self.log is not None:
                self.log.debug("TOOLBAR", f"!! Lock state changed enabled={self.attachment.locked_rect is not None}")
        except (ValueError, OSError) as error:
            if self.log is not None:
                self.log.debug("TOOLBAR", f"<< UI operation ended error_type={type(error).__name__}")
            self.notification.emit(str(error))
        self.sync()
        self.changed.emit()

    def capture(self):
        if self.log is not None:
            self.log.debug("TOOLBAR", f">> Capture requested")
        try:
            target = self.windows.read(self.attachment.target)
            saved_path = self.capture_service.capture(target)
            if self.log is not None:
                self.log.debug("TOOLBAR", f"<< Capture completed hwnd={target.handle_text} pid={target.pid}")
            self.capture_completed.emit(f"캡처 저장 완료: {saved_path}")
        except (NotImplementedError, ValueError, OSError) as error:
            if self.log is not None:
                self.log.debug("TOOLBAR", f"<< UI operation ended error_type={type(error).__name__}")
            self.notification.emit(str(error))

    def sync(self):
        self.window.toolbar.set_locked(self.attachment.locked_rect is not None)

    def hide(self):
        if self.log is not None:
            self.log.debug("TOOLBAR", "<< Toolbar kept visible for attached target")
        self.attachment.hidden = False
        self.update()
        self.changed.emit()

    def reveal(self):
        if self.log is not None:
            self.log.debug("TOOLBAR", f">> Reveal toolbar requested")
        self.attachment.hidden = False
        self.update()
        self.changed.emit()

    def reset_position(self):
        if self.log is not None:
            self.log.debug("TOOLBAR", f">> Reset toolbar position requested")
        self.attachment.offset = (0, 0)
        self.update()

    def drag(self, dx, dy):
        if self.log is not None:
            self.log.debug("TOOLBAR", f">> Toolbar drag requested dx={dx} dy={dy}")
        scale = self.window.devicePixelRatioF()
        x, y = self.attachment.offset
        self.attachment.offset = x + round(dx * scale), y + round(dy * scale)
        self.update()

    def update(self):
        previous = (self.attachment.target.title, self.attachment.locked_rect)
        try:
            # A popup may become foreground itself. Keep only this toolbar's
            # interaction alive; switching to another app must still hide it.
            menu = self.window.toolbar.menu
            handles = (int(menu.winId()), int(self.window.winId())) if menu.isVisible() else ()
            state = self.tracking.inspect(self.attachment.target, interaction_handles=handles)
        except OSError:
            self.detach_requested.emit(self.attachment.target.identity)
            return
        self.attachment.target = state.target
        if state.visible:
            try:
                self.locks.enforce(self.attachment, state.target)
            except (ValueError, OSError) as error:
                if self.log is not None:
                    self.log.debug("TOOLBAR", f"<< UI operation ended error_type={type(error).__name__}")
                self.locks.release(self.attachment)
                self.notification.emit(f"Lock 해제: {error}")
        self.sync()
        if previous != (self.attachment.target.title, self.attachment.locked_rect):
            self.window.setWindowTitle(f"GamaniJJom — {state.target.title}")
            self.changed.emit()
        pinned = self.window.toolbar.pin_button.isChecked()
        if not pinned and not state.show_toolbar:
            self.window.toolbar.menu.hide()
            self.window.hide()
            return
        self.window.show()
        try:
            if not pinned:
                self.tracking.place(int(self.window.winId()), state.target, self.attachment.offset)
            self._placement_error = None
        except OSError as error:
            if self.log is not None:
                self.log.debug("TOOLBAR", f"<< UI operation ended error_type={type(error).__name__}")
            if str(error) != self._placement_error:
                self.notification.emit(f"컨트롤러 배치 실패: {error}")
                self._placement_error = str(error)

    def dispose(self):
        if self.log is not None:
            self.log.debug("TOOLBAR", f"-- Toolbar disposed")
        self.locks.release(self.attachment)
        self.window.toolbar.menu.hide()
        self.window.hide()
        self.window.close()
        self.deleteLater()
