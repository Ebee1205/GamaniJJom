"""Shared dialog card with one title bar and replaceable body/footer widgets."""
from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget
from shiboken6 import isValid

SURFACE_MARGINS = (12, 8, 12, 12)
SURFACE_SPACING = 10
HEADER_MIN_HEIGHT = 24
HEADER_SPACING = 6
CLOSE_BUTTON_SIZE = 24


def show_dialog(dialog):
    """Open near the owner on its current screen, within the usable desktop."""
    if dialog.isMinimized():
        dialog.setWindowState(dialog.windowState() & ~Qt.WindowState.WindowMinimized)
    owner = dialog.parentWidget()
    opening = not dialog.isVisible()
    dialog.show()
    if opening and owner is not None:
        center = owner.frameGeometry().center()
        screen = QGuiApplication.screenAt(center) or owner.screen()
        work = screen.availableGeometry()
        frame = dialog.frameGeometry()
        x = max(work.x(), min(center.x() - frame.width() // 2,
                              work.x() + work.width() - frame.width()))
        y = max(work.y(), min(center.y() - frame.height() // 2,
                              work.y() + work.height() - frame.height()))
        dialog.move(x, y)
    dialog.raise_()
    dialog.activateWindow()


class _Slot:
    """본문/푸터처럼 위젯 하나를 갈아끼울 수 있는 영역.

    비어 있으면 container가 숨겨져서 공간을 차지하지 않는다.
    """

    def __init__(self, parent: QWidget):
        self.widget: QWidget | None = None
        self.container = QWidget(parent)
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.container.hide()

    def replace(self, widget: QWidget | None) -> None:
        """이전 위젯은 제거(deleteLater)하고 새 위젯을 넣는다. None이면 영역을 비운다."""
        previous = self.widget
        if previous is not None and isValid(previous):
            self.layout.removeWidget(previous)
            previous.hide()
            previous.deleteLater()

        self.widget = widget
        if widget is not None:
            self.layout.addWidget(widget)
            widget.show()
        self.container.setVisible(widget is not None)


class CmmDialogLayout(QFrame):
    """Use set_title(text), set_body(form_widget), and set_footer(actions_widget).

    Connect close_requested to the owning dialog's reject method. The template
    owns slot widgets and deletes a previous widget when its slot is replaced.
    """
    close_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dialogSurface")

        self._body_slot = _Slot(self)
        self._footer_slot = _Slot(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*SURFACE_MARGINS)
        layout.setSpacing(SURFACE_SPACING)
        layout.addWidget(self._build_header())
        layout.addWidget(self._body_slot.container)
        layout.addWidget(self._footer_slot.container)

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------
    @property
    def body(self) -> QWidget | None:
        return self._body_slot.widget

    @property
    def footer(self) -> QWidget | None:
        return self._footer_slot.widget

    @property
    def body_container(self) -> QWidget:
        return self._body_slot.container

    @property
    def footer_container(self) -> QWidget:
        return self._footer_slot.container

    @property
    def body_layout(self) -> QVBoxLayout:
        return self._body_slot.layout

    @property
    def footer_layout(self) -> QVBoxLayout:
        return self._footer_slot.layout

    def set_title(self, text: str) -> None:
        self.title_label.setText(text)
        self.title_label.setToolTip(text)

    def set_body(self, widget: QWidget | None) -> None:
        """Insert a body widget; replace/delete the previous widget when changed."""
        self._set_slot(self._body_slot, other=self._footer_slot, widget=widget)

    def set_footer(self, widget: QWidget | None) -> None:
        """Insert custom actions/status controls; None removes the footer."""
        self._set_slot(self._footer_slot, other=self._body_slot, widget=widget)

    # ------------------------------------------------------------------
    # 헤더 (제목 + 닫기 버튼, 드래그로 창 이동)
    # ------------------------------------------------------------------
    def _build_header(self) -> QWidget:
        self.header = QWidget(self)
        self.header.setObjectName("dialogHeader")
        self.header.setMinimumHeight(HEADER_MIN_HEIGHT)

        self.title_label = QLabel()
        self.title_label.setObjectName("dialogTitle")
        self.title_label.setTextFormat(Qt.TextFormat.PlainText)
        self.title_label.setWordWrap(True)

        self.close_button = QToolButton()
        self.close_button.setObjectName("closeButton")
        self.close_button.setText("✕")
        self.close_button.setAccessibleName("닫기")
        self.close_button.setToolTip("닫기")
        self.close_button.setFixedSize(CLOSE_BUTTON_SIZE, CLOSE_BUTTON_SIZE)
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.clicked.connect(self.close_requested.emit)

        bar = QHBoxLayout(self.header)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(HEADER_SPACING)
        bar.addWidget(self.title_label, 1)
        bar.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)

        # 제목 영역을 잡고 끌면 창이 이동한다
        self.header.installEventFilter(self)
        self.title_label.installEventFilter(self)
        return self.header

    def eventFilter(self, watched, event):
        if self._is_title_left_press(watched, event) and self._start_window_move():
            return True
        return super().eventFilter(watched, event)

    def _is_title_left_press(self, watched, event) -> bool:
        return (
            watched in (self.header, self.title_label)
            and event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        )

    def _start_window_move(self) -> bool:
        """OS 기본 창 이동을 시작한다. 시작하면 True."""
        window = self.window()
        handle = window.windowHandle()
        if handle is None or not handle.startSystemMove():
            return False
        log = getattr(window, "log", None)
        if log is not None:
            log.debug("DIALOG", ">> Dialog title bar drag requested")
        return True

    # ------------------------------------------------------------------
    # 슬롯 교체 + 검증
    # ------------------------------------------------------------------
    def _set_slot(self, slot: _Slot, other: _Slot, widget: QWidget | None) -> None:
        if widget is not None:
            self._validate_slot_widget(widget)
            if widget is other.widget:
                raise ValueError("A widget cannot occupy both dialog slots")
            if widget is slot.widget:
                return  # 이미 같은 위젯이 들어 있으면 할 일 없음
        slot.replace(widget)

    def _validate_slot_widget(self, widget: QWidget) -> None:
        if not isinstance(widget, QWidget):
            raise TypeError("Dialog slots accept QWidget or None")
        if not isValid(widget):
            raise ValueError("Dialog slots require a live QWidget")

        own_parts = (
            self, self.header, self.title_label, self.close_button,
            self.body_container, self.footer_container,
        )
        if widget in own_parts or widget.isAncestorOf(self):
            raise ValueError("A dialog slot cannot contain its own layout or parent")
