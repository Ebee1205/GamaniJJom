"""Popup mouse capture for hover-highlight and click-to-select a native window."""
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

class TargetPickerWidget(QWidget):
    selected = Signal(object)
    notification = Signal(str)

    def __init__(self, windows, tracking, toolbar_window):
        # A picker is a modal interaction, not a popup menu. Windows can close
        # a new Qt.Popup when the previous radial popup finishes deactivating.
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.windows, self.tracking, self.toolbar_window = windows, tracking, toolbar_window
        self.log = getattr(toolbar_window, "log", None)
        self._active = False
        self._candidate = None
        self._pressed = None
        self._right_previous = False
        self._right_armed = False
        self._hover_identity = None
        self._ticks = 0
        self.setFixedSize(320, 48)
        self.setWindowTitle("GamaniJJom - 창 선택 중")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setObjectName('targetPicker')
        label = QLabel('창 위로 이동 · 우클릭으로 확정 · Esc 취소', self)
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QVBoxLayout(self)
        layout.addWidget(label)
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self.refresh_candidate)
        self._input_timer = QTimer(self)
        self._input_timer.setInterval(16)
        self._input_timer.timeout.connect(self._poll_input)

    def _debug(self, message):
        if self.log is not None:
            self.log.debug("PICKER", message)

    def start(self):
        if self._active:
            self.stop("restart")
        self._hover_identity = None
        self._ticks = 0
        self._candidate = None
        self._pressed = None
        self._right_previous = False
        self._right_armed = False
        self._active = True
        try:
            self._right_previous, _escape = self.tracking.selection_input()
        except OSError as error:
            self.stop("input-error")
            self.notification.emit(str(error))
            return
        # Opening release belongs to the radial drag, not to confirmation.
        self._right_armed = not self._right_previous
        self._debug("Window selection started")
        self.show()
        self.raise_()
        self.setFocus(Qt.FocusReason.PopupFocusReason)
        self.grabMouse(QCursor(Qt.CursorShape.CrossCursor))
        self.grabKeyboard()
        self.refresh_candidate()
        if self._active:
            self._timer.start()
            self._input_timer.start()

    def stop(self, reason="cancelled"):
        if self._active:
            self._debug(f"Window selection stopped reason={reason}")
        self._active = False
        self._timer.stop()
        self._input_timer.stop()
        self._candidate = None
        self._pressed = None
        self._right_previous = False
        self._right_armed = False
        self.toolbar_window.show_candidate(None)
        if self.mouseGrabber() is self:
            self.releaseMouse()
        self.releaseKeyboard()
        self.hide()

    def refresh_candidate(self):
        if not self._active:
            return
        self._ticks += 1
        if self._ticks >= 500:
            self.stop("timeout")
            return
        try:
            self._candidate = self.windows.window_at_pointer(
                ignored_handles=(int(self.winId()), self.toolbar_window.candidate_handle),
            )
            cursor_x, cursor_y = self.tracking.cursor()
            # Native coordinates stay in the service layer.
            self.tracking.place_picker(int(self.winId()), cursor_x + 20, cursor_y + 20)
            info = self._candidate
            identity = info.identity if info is not None else None
            if identity != self._hover_identity:
                self._debug(f"Hover candidate hwnd={info.hwnd if info else None} "
                            f"title={info.title if info else None!r}")
                self._hover_identity = identity
            if info is None:
                self.toolbar_window.show_candidate(None)
            else:
                handle = self.toolbar_window.show_candidate(info.rect, selection=True)
                self.tracking.place_candidate(handle, info.rect)
        except OSError as error:
            self.stop("error")
            self.notification.emit(str(error))

    def _begin_right_press(self):
        if not self._active:
            return
        self.refresh_candidate()
        if self._active:
            self._right_armed = True
            self._right_previous = True
            self._pressed = self._candidate

    def _finish_right_release(self):
        if not self._active:
            return
        pressed = self._pressed
        self._pressed = None
        self._right_previous = False
        self._right_armed = True
        if pressed is None:
            return  # Ignore the release that opened this mode.
        self.refresh_candidate()
        if not self._active or self._candidate is None or self._candidate.identity != pressed.identity:
            return
        try:
            target = self.windows.read(self._candidate)
        except OSError as error:
            self.stop("invalid-target")
            self.notification.emit(str(error))
        else:
            self._debug(f"Selection confirmed hwnd={target.hwnd} title={target.title!r}")
            self.stop("selected")
            self.selected.emit(target)

    def _poll_input(self):
        if not self._active:
            return
        try:
            right_down, escape_down = self.tracking.selection_input()
        except OSError as error:
            self.stop("input-error")
            self.notification.emit(str(error))
            return
        if escape_down:
            self.stop("escape")
            return
        if not self._right_armed:
            self._right_previous = right_down
            if not right_down:
                self._right_armed = True
            return
        if right_down and not self._right_previous:
            self._begin_right_press()
        elif not right_down and self._right_previous:
            self._finish_right_release()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._begin_right_press()
        event.accept()  # Left-click does not confirm or cancel.

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._finish_right_release()
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.stop("escape")
            event.accept()
        else:
            super().keyPressEvent(event)

    def hideEvent(self, event):
        if self._active:
            self.stop("hidden")
        super().hideEvent(event)