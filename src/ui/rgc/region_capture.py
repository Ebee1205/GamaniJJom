"""Select and adjust a capture region in native desktop pixels."""
from dataclasses import replace

from PySide6.QtCore import QObject, QRectF, Qt, Signal
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


def _move(rect, dx, dy):
    return replace(rect, x=rect.x + dx, y=rect.y + dy)


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


class _SelectionSurface(QWidget):
    preview = Signal(object)
    finished = Signal(object)

    def __init__(self):
        super().__init__(None, FLOATING)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._start = None
        self._desktop_rect = None
        self._selection = None

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


class RegionCapture(QObject):
    """Keep the chosen rectangle relative to the current target's top-left."""
    capture_requested = Signal()
    notification = Signal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.rect = None
        self.selecting = False
        self._suspended = False
        self._target = None
        self._target_rect = None
        self._target_visible = True
        self._surface = _SelectionSurface()
        self._surface.preview.connect(self._present)
        self._surface.finished.connect(self._finish_selection)

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
        self._size.dragged.connect(self._move_region)
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
        self._lock.toggled.connect(self.refresh)
        self._close = QToolButton(self._bar)
        self._close.setText('닫기')
        self._close.clicked.connect(self.clear)
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
        self._grip.dragged.connect(self._resize_region)

    def start(self):
        if self.selecting:
            return
        self.selecting = True
        self._present(None)
        try:
            self._surface.begin()
        except OSError as error:
            self._finish_selection(None)
            self.notification.emit(str(error))

    def cancel_selection(self):
        if self.selecting:
            self._finish_selection(None)

    def _finish_selection(self, rect):
        self._surface.end()
        if rect is not None:
            origin = self._target_rect
            self.rect = _move(rect, -origin.x, -origin.y) if origin else rect
            self._lock.setChecked(False)
        self.selecting = False
        self.refresh()

    def clear(self):
        self.rect = None
        self._lock.setChecked(False)
        self.refresh()

    def observe(self, target, *, visible=True):
        origin = target.rect if target is not None else None
        reference = target.reference if target is not None else None
        if (reference, origin, visible) == (self._target, self._target_rect, self._target_visible):
            return
        # Preserve the last screen position on disconnect or a target switch.
        if self.rect is not None and reference != self._target:
            rect = self.screen_rect
            self.rect = _move(rect, -origin.x, -origin.y) if origin else rect
        self._target, self._target_rect, self._target_visible = reference, origin, visible
        if not self.selecting:
            self.refresh()

    @property
    def screen_rect(self):
        origin = self._target_rect
        return _move(self.rect, origin.x, origin.y) if self.rect and origin else self.rect

    def capture_rect(self):
        if not self._target_visible:
            raise OSError('연결된 창을 화면에 표시한 뒤 영역을 캡처하세요.')
        return self.screen_rect

    def set_suspended(self, suspended):
        self._suspended = suspended
        self.refresh()

    def refresh(self):
        if not self.selecting:
            self._present(self.screen_rect if self._target_visible and not self._suspended else None)

    def _move_region(self, dx, dy):
        if self.rect is not None:
            self.rect = _move(self.rect, dx, dy)
            self.refresh()

    def _resize_region(self, dx, dy):
        if self.rect is not None and not self._lock.isChecked():
            self.rect = replace(self.rect, width=max(MIN_SIZE, self.rect.width + dx),
                                height=max(MIN_SIZE, self.rect.height + dy))
            self.refresh()

    def _present(self, rect):
        if rect is None:
            for widget in (self._outline, self._bar, self._grip):
                widget.hide()
            return
        try:
            self._present_rect(rect)
        except OSError as error:
            self._present(None)
            self.notification.emit(str(error))

    def _present_rect(self, rect):
        _place(self._outline, rect)
        self._outline.raise_()
        self._size.setText(f'{rect.width} × {rect.height} px')
        self._coordinates.setText('창 기준' if self._target is not None else '절대 좌표')
        for control in self._bar_actions:
            control.setVisible(not self.selecting)

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

        show_grip = not self.selecting and not self._lock.isChecked()
        if show_grip:
            grip = 9
            _place(self._grip, WindowRect(rect.x + rect.width - grip,
                                         rect.y + rect.height - grip, grip, grip))
            self._grip.raise_()
        else:
            self._grip.hide()

    def dispose(self):
        self._surface.end()
        for widget in (self._surface, self._outline, self._bar, self._grip):
            widget.close()
            widget.deleteLater()
