"""On-demand attachment manager; no persistence is implied by this view."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.ui.cmp.window_list_cmp import WindowListComponent


class SettingsWindow(QWidget):
    attach_requested = Signal()
    reveal_requested = Signal(object)
    position_requested = Signal(object)
    detach_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsWindow")
        self.setWindowTitle("GamaniJJom — 연결된 프로그램·설정")
        self.resize(740, 380)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        header = QHBoxLayout()
        title = QLabel("연결된 프로그램")
        title.setObjectName("heading")
        header.addWidget(title)
        header.addStretch()
        connect = QPushButton("프로그램 연결…")
        connect.setObjectName("primaryButton")
        connect.clicked.connect(self.attach_requested.emit)
        header.addWidget(connect)
        layout.addLayout(header)
        self.window_list = WindowListComponent()
        layout.addWidget(self.window_list)
        actions = QHBoxLayout()
        self.actions = []
        for text, signal in (("컨트롤러 표시", self.reveal_requested),
                             ("위치·크기…", self.position_requested),
                             ("연결 해제", self.detach_requested)):
            button = QPushButton(text)
            button.setEnabled(False)
            button.clicked.connect(lambda checked=False, s=signal: self.emit_selected(s))
            self.actions.append(button)
            actions.addWidget(button)
        actions.addStretch()
        close = QPushButton("닫기")
        close.clicked.connect(self.hide)
        actions.addWidget(close)
        layout.addLayout(actions)
        self.status = QLabel("프로그램 연결은 이번 실행 동안 유지됩니다.")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        future = QLabel("준비 중: 화면 캡처 · 전역 단축키 · 설정 저장 및 자동 재연결")
        future.setObjectName("muted")
        future.setWordWrap(True)
        layout.addWidget(future)
        self.window_list.selection_changed.connect(self.update_actions)

    def update_actions(self, target):
        for button in self.actions:
            button.setEnabled(target is not None)

    def emit_selected(self, signal):
        target = self.window_list.selected_window()
        if target is not None:
            signal.emit(target)

    def closeEvent(self, event):
        self.hide()
        event.ignore()
