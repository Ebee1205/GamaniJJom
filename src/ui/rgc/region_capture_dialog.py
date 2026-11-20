"""Floating windows and pointer input for region capture."""
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

from src.adapters.windows import window_api
from src.models.window_schema import WindowRect
from src.ui.cmm.cmm_window_overlay import CmmWindowOverlay
from src.ui.resources import theme_color, theme_token

MIN_SIZE = 8
SELECTION_DIM = QColor(0, 0, 0, 100)
FLOATING = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.NoDropShadowWindowHint)


def _place(widget, rect):
    widget.show()
    window_api.set_rect(int(widget.winId()), rect)


class _RegionOutline(CmmWindowOverlay):
    """Draw the capture border on the shared click-through overlay window."""

    def paintEvent(self, event):
        rect = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        if rect.isEmpty():
            return
        highlight = theme_color('border-window-highlight')
        soft = QColor(highlight)
        soft.setAlpha(145)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, highlight)
        gradient.setColorAt(1.0, soft)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QBrush(gradient), 3))
        painter.drawRoundedRect(rect, 5, 5)


class _DragLabel(QLabel):
    dragged = Signal(int, int)

    def __init__(self, cursor, parent=None):
        super().__init__(parent)
        self.setCursor(cursor)
        self._previous = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._previous = window_api.cursor_position()

    def mouseMoveEvent(self, event):
        if self._previous is not None and event.buttons() & Qt.MouseButton.LeftButton:
            x, y = window_api.cursor_position()
            previous_x, previous_y = self._previous
            self._previous = x, y
            self.dragged.emit(x - previous_x, y - previous_y)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._previous = None


class RegionCaptureDialog(QWidget):
    """Non-modal selection surface, outline, capture bar and resize grip."""

    preview = Signal(object)
    finished = Signal(object)
    capture_requested = Signal()
    clear_requested = Signal()
    lock_requested = Signal(bool)
    moved = Signal(int, int)
    resized = Signal(int, int)

    def __init__(self):
        super().__init__(None, FLOATING)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._start = None
        self._desktop_rect = None
        self._selection = None
        self._outline = _RegionOutline()
        flags = FLOATING | Qt.WindowType.WindowDoesNotAcceptFocus
        self._bar = QWidget(None, flags)
        self._bar.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self._bar.setObjectName('captureRegionBar')
        layout = QHBoxLayout(self._bar)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(5)
        self._size = _DragLabel(Qt.CursorShape.SizeAllCursor, self._bar)
        self._size.setToolTip('드래그하여 영역 이동')
        self._size.dragged.connect(self.moved.emit)
        self._coordinates = QLabel(self._bar)
        self._coordinates.setObjectName('muted')
        self._capture = QToolButton(self._bar)
        self._capture.setObjectName('captureRegionButton')
        self._capture.setText('캡처')
        self._capture.setToolTip('선택 영역 캡처')
        self._capture.clicked.connect(self.capture_requested.emit)
        self._lock = QToolButton(self._bar)
        self._lock.setText('크기 고정')
        self._lock.setCheckable(True)
        self._lock.clicked[bool].connect(self.lock_requested.emit)
        self._close = QToolButton(self._bar)
        self._close.setText('닫기')
        self._close.clicked.connect(self.clear_requested.emit)
        self._bar_actions = (self._coordinates, self._lock, self._capture, self._close)
        for control in (self._size, *self._bar_actions):
            layout.addWidget(control)

        self._grip = _DragLabel(Qt.CursorShape.SizeFDiagCursor)
        self._grip.setWindowFlags(flags)
        self._grip.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._grip.setStyleSheet(
            f"background: {theme_token('border-window-highlight')}; border-radius: 2px;"
        )
        self._grip.setToolTip('드래그하여 크기 조절')
        self._grip.dragged.connect(self.resized.emit)

    def begin(self):
        monitors = [monitor.bounds for monitor in window_api.available_monitors()]
        left, top = min(r.x for r in monitors), min(r.y for r in monitors)
        right = max(r.x + r.width for r in monitors)
        bottom = max(r.y + r.height for r in monitors)
        self._desktop_rect = WindowRect(left, top, right - left, bottom - top)
        _place(self, self._desktop_rect)
        self.activateWindow()
        self.setFocus()
        self.grabKeyboard()

    def end(self):
        self._start = None
        self._selection = None
        if self.keyboardGrabber() is self:
            self.releaseKeyboard()
        self.hide()

    def paintEvent(self, event):
        shade = QPainterPath()
        shade.addRect(QRectF(self.rect()))
        if self._selection is not None:
            # The drag uses native desktop pixels while painting uses local Qt coordinates.
            selection, desktop = self._selection, self._desktop_rect
            scale = self.devicePixelRatioF()
            cutout = QRectF((selection.x - desktop.x) / scale, (selection.y - desktop.y) / scale,
                            selection.width / scale, selection.height / scale)
            shade.addRect(cutout)  # The default odd-even fill leaves this area clear.
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(event.rect(), Qt.GlobalColor.transparent)
        painter.fillPath(shade, SELECTION_DIM)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = window_api.cursor_position()
        elif event.button() == Qt.MouseButton.RightButton:
            self.finished.emit(None)

    def _drag_rect(self):
        x, y = window_api.cursor_position()
        start_x, start_y = self._start
        return WindowRect(min(x, start_x), min(y, start_y), abs(x - start_x), abs(y - start_y))

    def mouseMoveEvent(self, event):
        if self._start is not None:
            self._selection = self._selected_rect()
            self.update()
            self.preview.emit(self._selection)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._start is not None:
            self.finished.emit(self._selected_rect())

    def _selected_rect(self):
        rect = self._drag_rect()
        return rect if min(rect.width, rect.height) >= MIN_SIZE else None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.finished.emit(None)
        else:
            super().keyPressEvent(event)

    def present(self, rect, *, selecting, follows_window, locked):
        if rect is None:
            self.hide_preview()
            return

        _place(self._outline, rect)
        self._outline.raise_()
        self._size.setText(f'{rect.width} × {rect.height} px')
        self._coordinates.setText('창 연결' if follows_window else '연결 해제')
        for control in self._bar_actions:
            control.setVisible(not selecting)
        self._lock.setChecked(locked)

        monitor = window_api.monitor_at(rect.x, rect.y)
        work = monitor.work_area
        self._bar.adjustSize()
        scale = monitor.scale
        width, height = round(self._bar.width() * scale), round(self._bar.height() * scale)
        x = max(work.x, min(rect.x, work.x + work.width - width))
        y = rect.y - height - 4
        if y < work.y:
            y = rect.y + rect.height + 4
        y = max(work.y, min(y, work.y + work.height - height))
        _place(self._bar, WindowRect(x, y, width, height))
        self._bar.raise_()

        if not selecting and not locked:
            grip = 9
            _place(self._grip, WindowRect(rect.x + rect.width - grip,
                                         rect.y + rect.height - grip, grip, grip))
            self._grip.raise_()
        else:
            self._grip.hide()

    def hide_preview(self):
        for widget in (self._outline, self._bar, self._grip):
            widget.hide()

    def dispose(self):
        self.end()
        for widget in (self._outline, self._bar, self._grip, self):
            widget.close()
            widget.deleteLater()
