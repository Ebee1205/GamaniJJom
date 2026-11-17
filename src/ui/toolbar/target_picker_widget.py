"""Popup mouse capture for hover-highlight and click-to-select a native window."""
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class TargetPickerWidget(QWidget):
    selected = Signal(object)
    notification = Signal(str)

    def __init__(self, windows, tracking, toolbar_window):
        super().__init__(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.windows, self.tracking, self.toolbar_window = windows, tracking, toolbar_window
        self._active = False
        self._candidate = None
        self._pressed = None
        self._cancel_pending = False
        self._ticks = 0
        self.setFixedSize(256, 48)
        self.setStyleSheet('QWidget { background: #202833; color: #e3f2ed; border-radius: 8px; }')
        label = QLabel('창을 가리킨 뒤 클릭하여 지정 · Esc 취소', self)
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QVBoxLayout(self)
        layout.addWidget(label)
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self.refresh_candidate)

    def start(self):
        self._ticks = 0
        self._candidate = None
        self._pressed = None
        self._cancel_pending = False
        self._active = True
        self.show()
        self.setFocus(Qt.FocusReason.PopupFocusReason)
        self.grabMouse()
        self.grabKeyboard()
        self.refresh_candidate()
        self._timer.start()

    def stop(self):
        self._active = False
        self._timer.stop()
        self._candidate = None
        self._pressed = None
        self._cancel_pending = False
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
            self.stop()
            return
        try:
            self._candidate = self.windows.window_at_pointer(
                ignored_handles=(int(self.winId()), self.toolbar_window.candidate_handle),
            )
            cursor_x, cursor_y = self.tracking.cursor()
            # Native coordinates stay in the service layer.
            self.tracking.place_picker(int(self.winId()), cursor_x + 20, cursor_y + 20)
            info = self._candidate
            if info is None:
                self.toolbar_window.show_candidate(None)
            else:
                handle = self.toolbar_window.show_candidate(info.rect)
                self.tracking.place_candidate(handle, info.rect)
        except OSError as error:
            self.stop()
            self.notification.emit(str(error))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._cancel_pending = True
        elif event.button() == Qt.MouseButton.LeftButton:
            self.refresh_candidate()
            self._pressed = self._candidate
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton and self._cancel_pending:
            self.stop()
        elif event.button() == Qt.MouseButton.LeftButton and self._pressed is not None:
            pressed = self._pressed
            self._pressed = None
            self.refresh_candidate()
            if self._candidate is not None and self._candidate.identity == pressed.identity:
                try:
                    target = self.windows.read(self._candidate)
                except OSError as error:
                    self.notification.emit(str(error))
                else:
                    self.stop()
                    self.selected.emit(target)
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.stop()
            event.accept()
        else:
            super().keyPressEvent(event)

    def hideEvent(self, event):
        if self._active:
            self.stop()
        super().hideEvent(event)
