"""Compact, cancellable window selector; the controller validates and connects."""
from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from src.ui.cmm.cmm_dialog_layout import CmmDialogLayout
from src.ui.cmm.cmm_window_list import CmmWindowList, Column

CONNECTED_TEXT = "연결됨"
_NAV_KEYS = (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown)


class WdListDialog(QDialog):
    refresh_requested = Signal()
    selection_requested = Signal(object)

    def __init__(self, parent=None, log=None):
        flags = Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        super().__init__(parent, flags)
        self.log = log
        self._available = []
        self._connected_identity = None
        self._visible_count = 0
        self._error = ""

        self.setObjectName("WdListDialog")
        self.setWindowTitle("GamaniJJom - 창 목록")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumSize(520, 360)
        self.resize(600, 420)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.surface = CmmDialogLayout(self)
        self.surface.set_title("창 목록")
        self.surface.close_requested.connect(self.reject)
        outer.addWidget(self.surface)
        self.surface.set_body(self._build_body())
        self.surface.set_footer(self._build_footer())

        QShortcut(QKeySequence.StandardKey.Refresh, self, activated=self.refresh_requested.emit)
        self._update_status()

    # ---- UI construction ----------------------------------------------------------
    def _build_body(self):
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("창 이름 또는 PID 검색")
        self.search.setAccessibleName("창 검색")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_windows)
        self.search.returnPressed.connect(self.accept)
        self.search.installEventFilter(self)  # Up/Down keep working while typing
        self.refresh_button = QPushButton("새로고침")
        self.refresh_button.setToolTip("창 목록 새로고침 (F5)")
        self.refresh_button.setAutoDefault(False)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        row.addWidget(self.search, 1)
        row.addWidget(self.refresh_button)
        layout.addLayout(row)

        self.window_list = CmmWindowList()
        self.window_list.log = self.log
        self.window_list.show_only_columns((Column.PID, Column.STATUS))
        self.window_list.set_column_title(Column.TITLE, "창 이름")
        self.window_list.selection_changed.connect(self._selection_changed)
        self.window_list.window_activated.connect(lambda _target: self.accept())
        layout.addWidget(self.window_list, 1)
        return body

    def _build_footer(self):
        footer = QWidget()
        buttons = QHBoxLayout(footer)
        buttons.setContentsMargins(0, 0, 0, 0)
        self.status = QLabel()
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        buttons.addWidget(self.status, 1)
        self.cancel_button = QPushButton("취소")
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.clicked.connect(self.reject)
        self.confirm_button = QPushButton("연결")
        self.confirm_button.setObjectName("primaryButton")
        self.confirm_button.setDefault(True)
        self.confirm_button.setEnabled(False)
        self.confirm_button.clicked.connect(self.accept)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.confirm_button)
        return footer

    # ---- Public API ---------------------------------------------------------------
    def set_windows(self, windows, connected_identity=None):
        self._available = list(windows)
        self._connected_identity = connected_identity
        had_selection = self.window_list.selected_window() is not None
        self._error = ""
        self._filter_windows()
        # Only pre-select the connected window on first fill; a refresh must not
        # override what the user is currently browsing.
        if connected_identity is not None and not had_selection:
            self.window_list.select_identity(connected_identity)

    def set_error(self, message):
        self._error = message
        self._update_status()

    def set_busy(self, busy):
        self.refresh_button.setEnabled(not busy)
        if busy:
            self._error = ""
            self.status.setText("창 목록을 불러오는 중…")
        else:
            self._update_status()

    def accept(self):
        target = self.window_list.selected_window()
        if self.isVisible() and target is not None:
            self.selection_requested.emit(target)

    def finish_selection(self):
        super().accept()

    # ---- Internals ----------------------------------------------------------------
    def showEvent(self, event):
        super().showEvent(event)
        self.search.setFocus()

    def eventFilter(self, obj, event):
        if obj is self.search and event.type() == QEvent.Type.KeyPress and event.key() in _NAV_KEYS:
            QApplication.sendEvent(self.window_list, event)
            return True
        return super().eventFilter(obj, event)

    def _is_connected(self, window):
        return self._connected_identity is not None and window.identity == self._connected_identity

    def _filter_windows(self):
        text = self.search.text().strip().casefold()
        matches = [w for w in self._available if text in w.title.casefold() or text in str(w.pid)]
        matches.sort(key=lambda w: (not self._is_connected(w), w.title.casefold()))  # connected first
        self._visible_count = len(matches)

        statuses = {w.identity: (CONNECTED_TEXT if self._is_connected(w) else "") for w in matches}
        connected = (self._connected_identity,) if self._connected_identity is not None else ()
        if not self._available:
            self.window_list.set_empty_text("열려 있는 창이 없습니다.\n프로그램을 실행한 뒤 새로고침하세요.")
        else:
            self.window_list.set_empty_text(f"‘{self.search.text().strip()}’에 해당하는 창이 없습니다.")
        self.window_list.set_windows(matches, statuses=statuses, connected_identities=connected)

        # While searching, make Enter immediately usable by selecting the top hit.
        if text and matches and self.window_list.selected_window() is None:
            self.window_list.select_identity(matches[0].identity)

    def _selection_changed(self, target):
        self.confirm_button.setEnabled(target is not None)
        self._update_status()

    def _update_status(self):
        if self._error:
            self.status.setText(self._error)
            return
        target = self.window_list.selected_window()
        if target is not None:
            suffix = " (현재 연결됨)" if self._is_connected(target) else ""
            self.status.setText(f"선택: {target.title}{suffix}")
        elif self._visible_count:
            self.status.setText(f"창 {self._visible_count}개 · 연결할 창을 선택하세요.")
        else:
            self.status.setText("선택할 창이 없습니다.")