"""Geometry input and result display only. Controller validates and applies."""
from PySide6.QtCore import Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from src.models.window_schema import WindowRect


class PositionDialog(QDialog):
    apply_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.log = None
        self.target = None
        self.setWindowTitle("GamaniJJom — 위치·크기")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        self.title = QLabel()
        self.title.setObjectName("heading")
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        hint = QLabel("화면 픽셀 · 창 바깥 테두리 기준\n직접 적용하면 기존 Lock을 해제합니다.")
        hint.setObjectName("muted")
        layout.addWidget(hint)
        grid = QGridLayout()
        self.inputs = {}
        for index, (name, label) in enumerate((("x", "X"), ("y", "Y"), ("width", "너비"), ("height", "높이"))):
            field = QLineEdit()
            field.textEdited.connect(lambda text, key=name: self.log.debug("POSITION", f">> Input edited field={key} length={len(text)}") if self.log is not None else None)
            field.setValidator(QIntValidator(-2147483648 if index < 2 else 1, 2147483647, field))
            field.setAccessibleName(label)
            self.inputs[name] = field
            row, column = divmod(index, 2)
            grid.addWidget(QLabel(label), row * 2, column)
            grid.addWidget(field, row * 2 + 1, column)
        layout.addLayout(grid)
        self.status = QLabel()
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        buttons.addStretch()
        close = QPushButton("닫기")
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        self.apply_button = QPushButton("위치·크기 적용")
        self.apply_button.setObjectName("primaryButton")
        self.apply_button.clicked.connect(self.request_apply)
        buttons.addWidget(self.apply_button)
        layout.addLayout(buttons)

    def set_target(self, target):
        self.target = target
        self.title.setText(target.title)
        self.set_rect(target.rect)
        self.status.setText("일반 창으로 복원한 뒤 적용하세요.")
        self.set_busy(False)

    def set_rect(self, rect):
        for name, field in self.inputs.items():
            field.setText(str(getattr(rect, name)))

    def set_busy(self, busy):
        self.apply_button.setEnabled(not busy and self.target is not None)
        for field in self.inputs.values():
            field.setEnabled(not busy)

    def request_apply(self):
        if self.log is not None:
            self.log.debug("POSITION", f">> Position form submitted")
        if not all(field.hasAcceptableInput() for field in self.inputs.values()):
            self.status.setText("X/Y는 정수, 너비·높이는 1 이상의 정수로 입력하세요.")
            return
        try:
            rect = WindowRect(*(int(field.text()) for field in self.inputs.values()))
        except ValueError:
            self.status.setText("쉼표 없이 정수를 입력하세요.")
            return
        self.apply_requested.emit(rect)
