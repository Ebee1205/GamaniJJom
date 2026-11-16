"""Target selection instructions and list fallback; controller owns picking."""
from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from src.ui.cmp.window_list_cmp import WindowListComponent


class TargetPickerDialog(QDialog):
    target_requested = Signal(object)
    refresh_requested = Signal()
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GamaniJJom — 프로그램 연결")
        self.resize(700, 350)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        title = QLabel("컨트롤러를 붙일 창을 선택하세요")
        title.setObjectName("heading")
        layout.addWidget(title)
        self.status = QLabel("다른 프로그램 창을 클릭하거나 아래 목록에서 선택하세요. Esc로 취소합니다.")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.window_list = WindowListComponent()
        layout.addWidget(self.window_list)
        buttons = QHBoxLayout()
        refresh = QPushButton("새로고침 · F5")
        refresh.clicked.connect(self.refresh_requested.emit)
        buttons.addWidget(refresh)
        buttons.addStretch()
        cancel = QPushButton("취소")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.attach_button = QPushButton("선택한 창 연결")
        self.attach_button.setObjectName("primaryButton")
        self.attach_button.setEnabled(False)
        self.attach_button.clicked.connect(self.choose)
        buttons.addWidget(self.attach_button)
        layout.addLayout(buttons)
        self.window_list.selection_changed.connect(lambda info: self.attach_button.setEnabled(info is not None))
        self.window_list.window_activated.connect(lambda _: self.choose())
        self.shortcut = QShortcut(QKeySequence("F5"), self)
        self.shortcut.activated.connect(self.refresh_requested.emit)

    def choose(self):
        target = self.window_list.selected_window()
        if target is not None:
            self.target_requested.emit(target)

    def reject(self):
        self.cancelled.emit()
        super().reject()
