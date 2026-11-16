"""Reusable title/body/confirmation dialog with a Vue-style open_dialog API."""
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.ui.cmp.layout.dialog_layout import DialogLayout

DIALOG_WIDTH = 300


class CommonDialog(QDialog):
    def __init__(self, parent=None, log=None):
        super().__init__(parent, Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.log = log
        self.title = ""
        self.text = ""
        self.is_one_btn = False
        self.ok_text = "확인"
        self.on_confirm: Callable[[], None] | None = None

        self.setObjectName("commonDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setFixedWidth(DIALOG_WIDTH)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._build_surface())

    # ------------------------------------------------------------------
    # 공통 카드 템플릿에 본문과 버튼 위젯을 넣는다.
    # ------------------------------------------------------------------
    def _build_surface(self) -> DialogLayout:
        self.surface = DialogLayout(self)
        self.surface.close_requested.connect(self.reject)
        self.title_label = self.surface.title_label
        self.close_button = self.surface.close_button
        self.surface.set_body(self._build_text_label())
        footer = QWidget()
        footer.setLayout(self._build_buttons())
        self.surface.set_footer(footer)
        return self.surface

    def _build_text_label(self) -> QLabel:
        self.text_label = QLabel()
        self.text_label.setObjectName("commonDialogText")
        self.text_label.setTextFormat(Qt.TextFormat.RichText)
        self.text_label.setWordWrap(True)
        return self.text_label

    def _build_buttons(self) -> QHBoxLayout:
        """오른쪽 정렬: [취소] [확인]"""
        self.cancel_button = QPushButton("취소")
        self.cancel_button.clicked.connect(self.reject)

        self.confirm_button = QPushButton(self.ok_text)
        self.confirm_button.setObjectName("primaryButton")
        self.confirm_button.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(6)
        buttons.addStretch()
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.confirm_button)
        return buttons

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------
    @property
    def is_active(self) -> bool:
        return self.isVisible()

    @is_active.setter
    def is_active(self, active: bool):
        if active:
            self.show()
        else:
            self.on_confirm = None
            super().reject()

    def open_dialog(self, title: str, text: str, on_confirm: Callable[[], None] | None = None,
                    is_one_btn: bool = False, ok_text: str = "확인") -> None:
        """Open without blocking; close first, then run on_confirm exactly once.

        is_one_btn=True hides X and disables user cancellation with Esc/close.
        text accepts the subset of HTML supported by QLabel, including <br>.
        Setting is_active=False can dismiss either mode programmatically.
        """
        if on_confirm is not None and not callable(on_confirm):
            raise TypeError("on_confirm must be callable or None")
        self.title = title
        self.text = text
        self.on_confirm = on_confirm
        self.is_one_btn = bool(is_one_btn)
        self.ok_text = ok_text or "확인"

        self.setResult(QDialog.DialogCode.Rejected)
        self.setWindowTitle(title)
        self.surface.set_title(title)
        self.text_label.setText(text)
        self._apply_button_mode()

        self.adjustSize()
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.show()
        (self.confirm_button if self.is_one_btn else self.cancel_button).setFocus()
        self._debug(f">> Common dialog opened one_button={self.is_one_btn}")

    def _apply_button_mode(self) -> None:
        """한 버튼 모드: 확인만 표시, X/취소 숨김. 두 버튼 모드: 취소가 기본 버튼."""
        self.confirm_button.setText(self.ok_text)
        self.confirm_button.setAutoDefault(self.is_one_btn)
        self.confirm_button.setDefault(self.is_one_btn)
        self.cancel_button.setVisible(not self.is_one_btn)
        self.cancel_button.setAutoDefault(not self.is_one_btn)
        self.cancel_button.setDefault(not self.is_one_btn)
        self.close_button.setVisible(not self.is_one_btn)

    # ------------------------------------------------------------------
    # QDialog 오버라이드
    # ------------------------------------------------------------------
    def accept(self):
        if not self.is_active:
            return
        callback = self.on_confirm
        self.on_confirm = None
        super().accept()
        self._debug("<< Common dialog confirmed")
        if callback is not None:
            callback()

    def reject(self):
        if self.is_one_btn or not self.is_active:
            return
        self.on_confirm = None
        self._debug("<< Common dialog cancelled")
        super().reject()

    def closeEvent(self, event):
        if self.is_one_btn:
            event.ignore()
        else:
            self.reject()
            event.accept()

    def _debug(self, message: str) -> None:
        if self.log is not None:
            self.log.debug("DIALOG", message)
