"""Small non-activating translucent tool window."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from src.adapters.windows import window_api


class DragHandle(QLabel):
    moved = Signal(int, int)

    def __init__(self, parent):
        super().__init__("⠿", parent)
        self.setToolTip("드래그하여 툴바 위치 조정")
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self._start = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.globalPosition().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._start is not None:
            point = event.globalPosition().toPoint()
            delta = point - self._start
            self._start = point
            self.moved.emit(delta.x(), delta.y())
            event.accept()

    def mouseReleaseEvent(self, event):
        self._start = None
        event.accept()


class FloatingToolbar(QWidget):
    lock_requested = Signal()
    capture_requested = Signal()
    more_requested = Signal()
    dragged = Signal(int, int)

    def __init__(self, title):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle(f"GamaniJJom — {title}")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QFrame()
        surface.setObjectName("surface")
        layout = QHBoxLayout(surface)
        layout.setContentsMargins(7, 4, 7, 4)
        layout.setSpacing(4)
        self.handle = DragHandle(self)
        self.handle.moved.connect(self.dragged.emit)
        layout.addWidget(self.handle)
        self.lock_button = QPushButton("Lock")
        self.lock_button.setMinimumWidth(64)
        self.lock_button.setCheckable(True)
        self.lock_button.setToolTip("현재 위치·크기 고정 / 해제")
        self.lock_button.clicked.connect(lambda: self.lock_requested.emit())
        self.capture_button = QPushButton("Capture")
        self.capture_button.setToolTip("화면 캡처 (준비 중)")
        self.capture_button.clicked.connect(lambda: self.capture_requested.emit())
        self.more_button = QPushButton("···")
        self.more_button.setToolTip("프로그램 연결 · 좌표 설정 · 숨기기 · 분리")
        self.more_button.clicked.connect(lambda: self.more_requested.emit())
        for button in (self.lock_button, self.capture_button, self.more_button):
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            layout.addWidget(button)
        outer.addWidget(surface)
        self.setStyleSheet("""
            QFrame#surface { background: rgba(30,33,39,238); border-radius: 10px;
                             border: 1px solid #515866; }
            QLabel { color: #acb4c0; font-size: 21px; padding: 0 4px; }
            QPushButton { color: #edf0f5; background: transparent; border: none;
                          border-radius: 5px; padding: 6px 9px; }
            QPushButton:hover { background: #454c59; }
            QPushButton:checked { background: #487567; }
        """)
        self.adjustSize()
        self.setFixedSize(self.sizeHint())

    def sync_lock(self, enabled):
        self.lock_button.setChecked(enabled)
        self.lock_button.setText("Locked" if enabled else "Lock")

    def closeEvent(self, event):
        self.hide()
        event.ignore()
