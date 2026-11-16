"""Unified debug screen for available and attached program windows."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSplitter, QVBoxLayout, QWidget

from src.ui.cmp.window_list_cmp import WindowListComponent


class SettingsWindow(QWidget):
    target_requested = Signal(object)
    refresh_requested = Signal()
    quit_requested = Signal()
    reveal_requested = Signal(object)
    position_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.log = None
        self.setObjectName("settingsWindow")
        self.setWindowTitle("GamaniJJom — 프로그램 목록")
        self.resize(1120, 720)
        self.setMinimumSize(860, 560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        header = QHBoxLayout()
        title = QLabel("프로그램 전체 목록")
        title.setObjectName("heading")
        header.addWidget(title)
        header.addStretch()
        self.all_count = QLabel("0개")
        header.addWidget(self.all_count)
        layout.addLayout(header)
        splitter = QSplitter(Qt.Orientation.Vertical)
        available = QWidget()
        upper = QVBoxLayout(available)
        upper.setContentsMargins(0, 0, 0, 0)
        self.available_list = WindowListComponent()
        upper.addWidget(self.available_list)
        available_actions = QHBoxLayout()
        refresh = QPushButton("새로고침 · F5")
        refresh.clicked.connect(self.refresh_requested.emit)
        available_actions.addWidget(refresh)
        available_actions.addStretch()
        self.connect_button = QPushButton("선택한 프로그램 연결/변경")
        self.connect_button.setObjectName("primaryButton")
        self.connect_button.setEnabled(False)
        self.connect_button.clicked.connect(self.connect_selected)
        available_actions.addWidget(self.connect_button)
        upper.addLayout(available_actions)
        splitter.addWidget(available)
        attached = QWidget()
        lower = QVBoxLayout(attached)
        lower.setContentsMargins(0, 10, 0, 0)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        lower.addWidget(separator)
        connected_header = QHBoxLayout()
        connected_title = QLabel("현재 연결된 프로그램 목록")
        connected_title.setObjectName("heading")
        connected_header.addWidget(connected_title)
        connected_header.addStretch()
        self.connected_count = QLabel("0개")
        connected_header.addWidget(self.connected_count)
        lower.addLayout(connected_header)
        self.window_list = WindowListComponent()
        lower.addWidget(self.window_list)
        actions = QHBoxLayout()
        self.actions = []
        for text, signal in (("컨트롤러 표시", self.reveal_requested),
                             ("위치·크기…", self.position_requested)):
            button = QPushButton(text)
            button.setEnabled(False)
            button.clicked.connect(lambda checked=False, s=signal: self.emit_selected(s))
            self.actions.append(button)
            actions.addWidget(button)
        actions.addStretch()
        lower.addLayout(actions)
        splitter.addWidget(attached)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([340, 260])
        layout.addWidget(splitter)
        self.status = QLabel("프로그램 1개에 컨트롤러를 계속 표시합니다. 연결/변경 버튼으로 대상을 바꾸세요.")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.window_list.selection_changed.connect(self.update_actions)
        self.available_list.selection_changed.connect(lambda target: self.connect_button.setEnabled(target is not None))
        self.available_list.window_activated.connect(lambda _: self.connect_selected())
        self.refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        self.refresh_shortcut.activated.connect(self.refresh_requested.emit)

    def connect_selected(self):
        target = self.available_list.selected_window()
        if target is not None:
            if self.log is not None:
                self.log.debug("UI", f">> Program connection selected hwnd={target.handle_text} pid={target.pid}")
            self.target_requested.emit(target)

    def update_actions(self, target):
        for button in self.actions:
            button.setEnabled(target is not None)

    def emit_selected(self, signal):
        if self.log is not None:
            self.log.debug("SETTINGS", f">> Selected window action requested")
        target = self.window_list.selected_window()
        if target is not None:
            signal.emit(target)

    def closeEvent(self, event):
        if self.log is not None:
            self.log.debug("UI", ">> Main window close requested")
        self.quit_requested.emit()
        event.accept()
