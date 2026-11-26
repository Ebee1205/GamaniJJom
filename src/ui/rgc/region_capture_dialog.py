"""Floating windows and pointer input for region capture."""
from PySide6.QtCore import QLocale, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QIcon, QIntValidator, QLinearGradient, QPainter, QPainterPath,
                           QPalette, QPen, QPixmap)
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QToolButton, QWidget

from src.adapters.windows import window_api
from src.models.window_schema import WindowRect
from src.ui.cmm.cmm_window_flags import REGION_GRIP_WINDOW_FLAGS, REGION_WINDOW_FLAGS
from src.ui.cmm.cmm_window_overlay import CmmWindowOverlay
from src.ui.resources import icon, theme_color, theme_token

MIN_SIZE = 8
CORNER_GRIP = 11
EDGE_GRIP = 9
ICON_SIZE = QSize(16, 16)
# 켜짐(True)/꺼짐(False) 아이콘 이름. 상태와 반대로 보이면 이름만 서로 바꾸세요.
LOCK_ICON = {True: 'lock', False: 'unlock'}
PIN_ICON = {True: 'pin', False: 'pin'}
OFF_OPACITY = 0.45  # 꺼진 토글 아이콘을 흐리게 보여 켜짐/꺼짐을 구분
SELECTION_DIM = QColor(0, 0, 0, 100)

# edge: (가로 비율, 세로 비율, 커서)
_HANDLES = {
    'nw': (0.0, 0.0, Qt.CursorShape.SizeFDiagCursor),
    'n': (0.5, 0.0, Qt.CursorShape.SizeVerCursor),
    'ne': (1.0, 0.0, Qt.CursorShape.SizeBDiagCursor),
    'e': (1.0, 0.5, Qt.CursorShape.SizeHorCursor),
    'se': (1.0, 1.0, Qt.CursorShape.SizeFDiagCursor),
    's': (0.5, 1.0, Qt.CursorShape.SizeVerCursor),
    'sw': (0.0, 1.0, Qt.CursorShape.SizeBDiagCursor),
    'w': (0.0, 0.5, Qt.CursorShape.SizeHorCursor),
}


def resize_rect(rect, edge, dx, dy):
    """edge('n', 'se', 'w' 등) 방향으로 dx, dy만큼 드래그한 새 영역. 최소 크기를 보장."""
    x, y, w, h = rect.x, rect.y, rect.width, rect.height
    if 'w' in edge:
        dx = min(dx, w - MIN_SIZE)
        x, w = x + dx, w - dx
    if 'e' in edge:
        w = max(MIN_SIZE, w + dx)
    if 'n' in edge:
        dy = min(dy, h - MIN_SIZE)
        y, h = y + dy, h - dy
    if 's' in edge:
        h = max(MIN_SIZE, h + dy)
    return WindowRect(x, y, w, h)


def _place(widget, rect):
    widget.show()
    window_api.set_rect(int(widget.winId()), rect)


def _glyph_icon(kind, color):
    """테마 아이콘에 없는 단순 도형(닫기 X, 이동 점 6개)을 직접 그린다."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if kind == 'close':
        painter.setPen(QPen(color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(10, 10, 22, 22)
        painter.drawLine(22, 10, 10, 22)
    else:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        for x in (12, 20):
            for y in (8, 16, 24):
                painter.drawEllipse(QPointF(x, y), 2, 2)
    painter.end()
    return QIcon(pixmap)


def _dimmed(source):
    pixmap = source.pixmap(QSize(32, 32))
    faded = QPixmap(pixmap.size())
    faded.fill(Qt.GlobalColor.transparent)
    painter = QPainter(faded)
    painter.setOpacity(OFF_OPACITY)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return QIcon(faded)


def _state_icons(names):
    """{켜짐: 원본 아이콘, 꺼짐: 흐린 아이콘}"""
    return {True: icon(names[True]), False: _dimmed(icon(names[False]))}


def _rgba(color, alpha):
    return f'rgba({color.red()}, {color.green()}, {color.blue()}, {alpha})'


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
    """Non-modal selection surface, outline, capture bar and resize handles."""

    preview = Signal(object)
    finished = Signal(object)
    capture_requested = Signal()
    clear_requested = Signal()
    lock_requested = Signal(bool)
    pin_requested = Signal(bool)
    moved = Signal(int, int)
    edge_resized = Signal(str, int, int)  # edge, dx, dy
    size_requested = Signal(int, int)

    def __init__(self):
        super().__init__(None, REGION_WINDOW_FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._start = None
        self._desktop_rect = None
        self._selection = None
        self._shown_size = None
        self._outline = _RegionOutline()

        highlight = theme_color('border-window-highlight')
        self._bar = QWidget(None, REGION_WINDOW_FLAGS)
        self._bar.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self._bar.setObjectName('captureRegionBar')
        self._bar.setStyleSheet(
            "QToolButton#captureRegionIcon { border: none; border-radius: 5px; background: transparent; }"
            f"QToolButton#captureRegionIcon:hover {{ background: {_rgba(highlight, 40)}; }}"
            f"QToolButton#captureRegionIcon[active=\"true\"] {{ background: {_rgba(highlight, 120)}; }}"
            f"QToolButton#captureRegionIcon[active=\"true\"]:hover {{ background: {_rgba(highlight, 150)}; }}"
            "QFrame#captureRegionDivider { background: rgba(128, 128, 128, 90); border: none; }"
        )
        glyph_color = self._bar.palette().color(QPalette.ColorRole.ButtonText)

        layout = QHBoxLayout(self._bar)
        layout.setContentsMargins(6, 4, 4, 4)
        layout.setSpacing(4)

        # 이동 손잡이 (아이콘)
        self._move_handle = _DragLabel(Qt.CursorShape.SizeAllCursor, self._bar)
        self._move_handle.setObjectName('captureRegionMoveHandle')
        self._move_handle.setPixmap(_glyph_icon('grip', glyph_color).pixmap(ICON_SIZE))
        self._move_handle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._move_handle.setFixedSize(24, 24)
        self._move_handle.setAccessibleName('캡처 영역 이동 손잡이')
        self._move_handle.setToolTip('드래그하여 영역 이동')
        self._move_handle.dragged.connect(self.moved.emit)

        # 크기 입력
        self._width = self._size_field('너비')
        self._height = self._size_field('높이')
        separator = QLabel('×', self._bar)
        self._size = _DragLabel(Qt.CursorShape.SizeAllCursor, self._bar)
        self._size.setToolTip('드래그하여 영역 이동')
        self._size.dragged.connect(self.moved.emit)
        for field in (self._width, self._height):
            field.editingFinished.connect(self._apply_size)  # Enter 또는 포커스 이동 시 적용

        # 아이콘 전용 버튼들
        self._lock = self._icon_button(_state_icons(LOCK_ICON), '크기 고정', checkable=True)
        self._lock.clicked[bool].connect(self.lock_requested.emit)
        self._pin = self._icon_button(_state_icons(PIN_ICON), '위치 고정', checkable=True)
        self._pin.clicked[bool].connect(self.pin_requested.emit)

        self._capture = QToolButton(self._bar)
        self._capture.setObjectName('captureRegionButton')
        self._capture.setIcon(icon('camera'))
        self._capture.setIconSize(ICON_SIZE)
        self._capture.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._capture.setFixedSize(30, 26)
        self._capture.setAccessibleName('선택 영역 캡처')
        self._capture.setToolTip('선택 영역 캡처')
        self._capture.clicked.connect(self.capture_requested.emit)

        self._close = self._icon_button(_glyph_icon('close', glyph_color), '닫기')
        self._close.clicked.connect(self.clear_requested.emit)

        # [이동] [너비 × 높이 px] | [크기 고정] [위치 고정] | [캡처] [닫기]
        self._bar_controls = (
            self._move_handle, self._width, separator, self._height, self._size,
            self._divider(),
            self._lock, self._pin,
            self._divider(),
            self._capture, self._close,
        )
        for control in self._bar_controls:
            layout.addWidget(control)

        # 8방향 리사이즈 핸들 (꼭짓점은 크게, 변 중앙은 작게)
        self._handles = {}
        grip_style = (f"background: white; border: 2px solid {theme_token('border-window-highlight')};"
                      " border-radius: 2px;")
        for edge, (_, _, cursor) in _HANDLES.items():
            handle = _DragLabel(cursor)
            handle.setWindowFlags(REGION_GRIP_WINDOW_FLAGS)
            handle.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            handle.setStyleSheet(grip_style)
            handle.setToolTip('드래그하여 크기 조절')
            handle.dragged.connect(lambda dx, dy, e=edge: self.edge_resized.emit(e, dx, dy))
            self._handles[edge] = handle

    def _icon_button(self, icons, tooltip, *, checkable=False):
        """icons: QIcon, 또는 checkable일 때 {켜짐: QIcon, 꺼짐: QIcon}."""
        button = QToolButton(self._bar)
        button.setObjectName('captureRegionIcon')
        button.setIconSize(ICON_SIZE)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setCheckable(checkable)
        button.setFixedSize(26, 26)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        if checkable:
            # :checked 의사 상태 대신 'active' 속성으로 표시해 테마 스타일과 충돌하지 않게 한다.
            button.toggled.connect(lambda on, b=button, i=icons: self._show_state(b, i, on))
            self._show_state(button, icons, False)
        else:
            button.setIcon(icons)
        return button

    @staticmethod
    def _show_state(button, icons, on):
        button.setIcon(icons[bool(on)])
        button.setProperty('active', bool(on))
        button.style().unpolish(button)
        button.style().polish(button)

    def _divider(self):
        line = QFrame(self._bar)
        line.setObjectName('captureRegionDivider')
        line.setFixedSize(1, 16)
        return line

    def _size_field(self, label):
        field = QLineEdit(self._bar)
        field.setObjectName('captureRegionSize')
        field.setAccessibleName(f'영역 {label} (px)')
        field.setToolTip(f'영역 {label} (px) · Enter로 적용')
        field.setAlignment(Qt.AlignmentFlag.AlignRight)
        field.setFixedWidth(58)
        validator = QIntValidator(MIN_SIZE, MIN_SIZE, field)
        locale = QLocale.c()
        locale.setNumberOptions(QLocale.NumberOption.RejectGroupSeparator)
        validator.setLocale(locale)
        field.setValidator(validator)
        return field

    def _apply_size(self):
        if self._width.isReadOnly():
            return
        if not (self._width.hasAcceptableInput() and self._height.hasAcceptableInput()):
            return
        size = (int(self._width.text()), int(self._height.text()))
        if size != self._shown_size:
            self.size_requested.emit(*size)

    def begin(self):
        monitors = [monitor.bounds for monitor in window_api.available_monitors()]
        left, top = min(r.x for r in monitors), min(r.y for r in monitors)
        right = max(r.x + r.width for r in monitors)
        bottom = max(r.y + r.height for r in monitors)
        self._desktop_rect = WindowRect(left, top, right - left, bottom - top)
        self._shown_size = None
        self._width.validator().setTop(self._desktop_rect.width)
        self._height.validator().setTop(self._desktop_rect.height)
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

    def present(self, rect, *, selecting, follows_window, locked, pinned):
        if rect is None:
            self.hide_preview()
            return

        _place(self._outline, rect)
        self._outline.raise_()
        self._size.setText(f'{rect.width} × {rect.height} px' if selecting else 'px')
        for control in self._bar_controls:
            control.setVisible(not selecting or control is self._size)
        if not selecting:
            self._show_size(rect.width, rect.height, locked)
            self._pin.setChecked(pinned)
            if pinned:
                tip = '위치 고정 해제 (창을 다시 따라감)'
            elif follows_window:
                tip = '위치 고정: 창이 움직여도 이 화면 좌표에 유지'
            else:
                tip = '위치 고정: 현재 창 연결이 해제된 상태입니다'
            self._pin.setToolTip(tip)
            self._pin.setAccessibleName('위치 고정 해제' if pinned else '위치 고정')
            self._move_handle.setEnabled(not pinned)
            self._size.setEnabled(not pinned)

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
            for edge, (fx, fy, _) in _HANDLES.items():
                handle = self._handles[edge]
                grip = CORNER_GRIP if len(edge) == 2 else EDGE_GRIP
                _place(handle, WindowRect(round(rect.x + rect.width * fx - grip / 2),
                                          round(rect.y + rect.height * fy - grip / 2), grip, grip))
                handle.raise_()
        else:
            for handle in self._handles.values():
                handle.hide()

    def _show_size(self, width, height, locked):
        size = (width, height)
        if self._shown_size != size or self._width.isReadOnly() != locked:
            self._shown_size = size
            self._width.setText(str(width))
            self._height.setText(str(height))
        self._width.setReadOnly(locked)
        self._height.setReadOnly(locked)
        self._lock.setChecked(locked)
        tip = ('크기 고정 해제' if locked
               else '크기 고정: 크기 입력과 모서리·변 핸들을 잠급니다')
        self._lock.setToolTip(tip)
        self._lock.setAccessibleName('크기 고정 해제' if locked else '크기 고정')

    def hide_preview(self):
        for widget in (self._outline, self._bar, *self._handles.values()):
            widget.hide()

    def dispose(self):
        self.end()
        for widget in (self._outline, self._bar, *self._handles.values(), self):
            widget.close()
            widget.deleteLater()