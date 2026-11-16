"""Geometry input and result display only. Controller validates and applies."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontMetrics, QIntValidator
from PySide6.QtWidgets import (
    QDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from src.models.window_schema import WindowRect
from src.ui.cmm.cmm_dialog_layout import CmmDialogLayout

TITLE_MAX_WIDTH = 220


class WdSizeDialog(QDialog):
    apply_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.log = None
        self.target = None
        self.setObjectName("positionDialog")
        self.setWindowTitle("GamaniJJom — 위치·크기")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(300)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.surface = CmmDialogLayout(self)
        outer.addWidget(self.surface)
        self.title_bar = self.surface.header
        self.title = self.surface.title_label
        self.close_button = self.surface.close_button
        self.surface.set_title("위치·크기")
        self.surface.close_requested.connect(self.reject)

        # Inputs: [X] [Y] / [W] [H]
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        self.inputs = {}
        fields = (("x", "X", "X"), ("y", "Y", "Y"), ("width", "W", "너비"), ("height", "H", "높이"))
        for index, (name, short, accessible) in enumerate(fields):
            field = QLineEdit()
            field.setObjectName("compactField")
            field.textEdited.connect(
                lambda text, key=name: self.log.debug("POSITION", f">> Input edited field={key} length={len(text)}")
                if self.log is not None else None
            )
            field.setValidator(QIntValidator(-2147483648 if index < 2 else 1, 2147483647, field))
            field.setAccessibleName(accessible)
            self.inputs[name] = field
            label = QLabel(short)
            label.setObjectName("fieldLabel")
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            label.setMinimumWidth(14)
            row, column = divmod(index, 2)
            grid.addWidget(label, row, column * 2)
            grid.addWidget(field, row, column * 2 + 1)
        self.surface.set_body(body)

        # Status + apply
        footer_widget = QWidget()
        footer = QHBoxLayout(footer_widget)
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        self.status = QLabel()
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        footer.addWidget(self.status, 1)
        self.apply_button = QPushButton("적용")
        self.apply_button.setObjectName("primaryButton")
        self.apply_button.setToolTip("직접 적용하면 기존 Lock을 해제합니다.")
        self.apply_button.setDefault(True)
        self.apply_button.clicked.connect(self.request_apply)
        footer.addWidget(self.apply_button, 0, Qt.AlignBottom)
        self.surface.set_footer(footer_widget)

    # --- public API (unchanged) --------------------------------------------
    def set_target(self, target):
        self.target = target
        elided = QFontMetrics(self.title.font()).elidedText(target.title, Qt.ElideRight, TITLE_MAX_WIDTH)
        self.title.setText(elided)
        self.title.setToolTip(target.title)
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
            self.log.debug("POSITION", ">> Position form submitted")
        if not all(field.hasAcceptableInput() for field in self.inputs.values()):
            self.status.setText("X/Y는 정수, W/H는 1 이상의 정수로 입력하세요.")
            return
        try:
            rect = WindowRect(*(int(field.text()) for field in self.inputs.values()))
        except ValueError:
            self.status.setText("쉼표 없이 정수를 입력하세요.")
            return
        self.apply_requested.emit(rect)
