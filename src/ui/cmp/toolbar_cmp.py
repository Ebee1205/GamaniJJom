"""Drag handle, action buttons and their menu. No service or native API calls."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu

from src.ui.cmp.button_cmp import ButtonComponent


class DragHandle(QLabel):
    dragged = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__("⠿", parent)
        self.setObjectName("dragHandle")
        self.setFixedWidth(18)
        self.setToolTip("드래그하여 컨트롤러 위치 조정")
        self.setAccessibleName("컨트롤러 이동 핸들")
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self._previous = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._previous = event.globalPosition().toPoint()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._previous is not None and event.buttons() & Qt.MouseButton.LeftButton:
            point = event.globalPosition().toPoint()
            delta = point - self._previous
            self._previous = point
            self.dragged.emit(delta.x(), delta.y())
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._previous = None
        super().mouseReleaseEvent(event)


class ToolbarComponent(QFrame):
    lock_requested = Signal()
    capture_requested = Signal()
    position_requested = Signal()
    capture_options_requested = Signal()
    settings_requested = Signal()
    attach_requested = Signal()
    detach_requested = Signal()
    hide_requested = Signal()
    reset_requested = Signal()
    quit_requested = Signal()
    dragged = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("toolbarSurface")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(3)
        self.handle = DragHandle(self)
        self.handle.dragged.connect(self.dragged.emit)
        layout.addWidget(self.handle)
        self.lock_button = ButtonComponent("unlock", "현재 위치·크기 고정", self, checkable=True)
        self.capture_button = ButtonComponent("capture", "화면 캡처 · 준비 중", self)
        self.more_button = ButtonComponent("more", "더보기", self)
        self.lock_button.clicked.connect(lambda: self.lock_requested.emit())
        self.lock_button.secondary_requested.connect(self.position_requested.emit)
        self.capture_button.clicked.connect(self.capture_requested.emit)
        self.capture_button.secondary_requested.connect(self.capture_options_requested.emit)
        for button in (self.lock_button, self.capture_button, self.more_button):
            layout.addWidget(button)
        self.menu = QMenu(self)
        for text, signal in (
            ("프로그램 연결…", self.attach_requested),
            ("위치·크기 설정…", self.position_requested),
            ("연결된 프로그램·설정…", self.settings_requested),
            ("부착 위치 초기화", self.reset_requested),
            ("컨트롤러 숨기기", self.hide_requested),
            ("연결 해제 · Lock 해제", self.detach_requested),
        ):
            self.menu.addAction(text, signal.emit)
        self.menu.addSeparator()
        self.menu.addAction("종료", self.quit_requested.emit)
        self.more_button.clicked.connect(self.show_menu)

    def show_menu(self):
        self.menu.popup(self.more_button.mapToGlobal(self.more_button.rect().bottomLeft()))

    def set_locked(self, enabled: bool):
        self.lock_button.setChecked(enabled)
        self.lock_button.set_icon("lock" if enabled else "unlock")
        text = "위치·크기 고정 중 · 클릭하여 해제" if enabled else "현재 위치·크기 고정"
        self.lock_button.setToolTip(text + " · 우클릭: 좌표 설정")
        self.lock_button.setAccessibleName(text)
