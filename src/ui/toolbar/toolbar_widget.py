"""Drag handle, action buttons and their menu. No service or native API calls."""
from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu

from src.ui.cmm.cmm_button import CmmButton


class DragHandle(QLabel):
    dragged = Signal(int, int)  # Compatibility signal; controller uses gesture boundaries.
    drag_started = Signal()
    drag_moved = Signal()
    drag_finished = Signal()
    drag_cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__("⠿", parent)
        self.log = None
        self.setObjectName("dragHandle")
        self.setFixedWidth(18)
        self.setToolTip("드래그하여 이동 · Alt: 점착 억제 · Esc: 드래그 취소")
        self.setAccessibleName("툴바 이동 손잡이")
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self._previous = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._previous = event.globalPosition().toPoint()
            self.drag_started.emit()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._previous is not None and event.buttons() & Qt.MouseButton.LeftButton:
            point = event.globalPosition().toPoint()
            delta = point - self._previous
            self._previous = point
            self.dragged.emit(delta.x(), delta.y())
            self.drag_moved.emit()
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._previous is not None:
            self._previous = None
            self.drag_finished.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def cancel_drag(self):
        if self._previous is not None:
            self._previous = None
            if self.mouseGrabber() is self:
                self.releaseMouse()
            self.drag_cancelled.emit()

    def event(self, event):
        if event.type() in (QEvent.Type.UngrabMouse, QEvent.Type.Hide):
            self.cancel_drag()
        return super().event(event)


class ToolbarWidget(QFrame):
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
    drag_started = Signal()
    drag_moved = Signal()
    drag_finished = Signal()
    drag_cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.log = None
        self.setObjectName("toolbarSurface")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(3)
        self.handle = DragHandle(self)
        self.handle.dragged.connect(self.dragged.emit)
        self.handle.drag_started.connect(self.drag_started.emit)
        self.handle.drag_moved.connect(self.drag_moved.emit)
        self.handle.drag_finished.connect(self.drag_finished.emit)
        self.handle.drag_cancelled.connect(self.drag_cancelled.emit)
        layout.addWidget(self.handle)
        self.lock_button = CmmButton("unlock", "현재 위치·크기 고정", self, checkable=True)
        self.pin_button = CmmButton("pin", "툴바 위치 고정 및 항상 위에 표시", self, checkable=True)
        self.capture_button = CmmButton("capture", "화면 캡처 · 준비 중", self)
        self.more_button = CmmButton("more", "더보기", self)
        self.lock_button.clicked.connect(lambda: self.lock_requested.emit())
        self.lock_button.secondary_requested.connect(self.position_requested.emit)
        self.capture_button.clicked.connect(self.capture_requested.emit)
        self.capture_button.secondary_requested.connect(self.capture_options_requested.emit)
        for button in (self.pin_button, self.lock_button, self.capture_button, self.more_button):
            layout.addWidget(button)
        self.menu = QMenu(self)
        menu = self.menu
        menu.triggered.connect(lambda action: self.log.debug("TOOLBAR", f">> Menu action selected index={menu.actions().index(action)}") if self.log is not None else None)
        self.menu.aboutToHide.connect(lambda: self.log.debug("TOOLBAR", "<< More menu closed") if self.log is not None else None)
        for text, signal in (
            ("프로그램 목록…", self.attach_requested),
            ("설정…", self.settings_requested),
            ("위치·크기 설정…", self.position_requested),
            ("부착 위치 초기화", self.reset_requested),
        ):
            self.menu.addAction(text, signal.emit)
        self.menu.addSeparator()
        self.menu.addAction("종료", self.quit_requested.emit)
        self.more_button.clicked.connect(self.show_menu)

    def show_menu(self):
        if self.log is not None:
            self.log.debug("TOOLBAR", f">> More menu requested")
        self.menu.popup(self.more_button.mapToGlobal(self.more_button.rect().bottomLeft()))

    def set_locked(self, enabled: bool):
        self.lock_button.setChecked(enabled)
        self.lock_button.set_icon("lock" if enabled else "unlock")
        text = "위치·크기 고정 중 · 클릭하여 해제" if enabled else "현재 위치·크기 고정"
        self.lock_button.setToolTip(text + " · 우클릭: 좌표 설정")
        self.lock_button.setAccessibleName(text)
