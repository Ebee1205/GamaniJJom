"""Compact, cancellable window selector; the controller validates and connects."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel

from src.ui.cmm.cmm_dialog_layout import CmmDialogLayout
from src.ui.cmm.cmm_window_list import CmmWindowList


class WindowListDialog(QDialog):
    refresh_requested = Signal()
    selection_requested = Signal(object)

    def __init__(self, parent=None, log=None):
        flags = Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        super().__init__(parent, flags)
        self.log = log
        self.setObjectName('windowListDialog')
        self.setWindowTitle('GamaniJJom - 창 목록')
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumSize(520, 360)
        self.resize(600, 420)
        self._available = []
        self._connected_identity = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.surface = CmmDialogLayout(self)
        self.surface.set_title('창 목록')
        self.surface.close_requested.connect(self.reject)
        outer.addWidget(self.surface)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('창 이름 또는 PID 검색')
        self.search.setAccessibleName('창 검색')
        self.search.textChanged.connect(self._filter_windows)
        self.refresh_button = QPushButton('새로고침')
        self.refresh_button.setAutoDefault(False)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        row.addWidget(self.search, 1)
        row.addWidget(self.refresh_button)
        layout.addLayout(row)
        self.window_list = CmmWindowList()
        self.window_list.log = log
        self.window_list.setHeaderLabels(['창 이름', 'PID', 'HWND', 'X', 'Y', '너비', '높이', '상태', '오프셋'])
        for column in range(2, 9):
            self.window_list.hideColumn(column)
        self.window_list.selection_changed.connect(self._selection_changed)
        self.window_list.window_activated.connect(lambda _target: self.accept())
        layout.addWidget(self.window_list, 1)
        self.surface.set_body(body)
        footer = QWidget()
        buttons = QHBoxLayout(footer)
        buttons.setContentsMargins(0, 0, 0, 0)
        self.status = QLabel('연결할 창을 선택하세요.')
        self.status.setObjectName('status')
        self.status.setWordWrap(True)
        buttons.addWidget(self.status, 1)
        self.cancel_button = QPushButton('취소')
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.clicked.connect(self.reject)
        self.confirm_button = QPushButton('연결')
        self.confirm_button.setObjectName('primaryButton')
        self.confirm_button.setDefault(True)
        self.confirm_button.setEnabled(False)
        self.confirm_button.clicked.connect(self.accept)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.confirm_button)
        self.surface.set_footer(footer)

    def set_windows(self, windows, connected_identity=None):
        self._available = list(windows)
        self._connected_identity = connected_identity
        self._filter_windows()
        if connected_identity is not None:
            self.window_list.select_identity(connected_identity)

    def _filter_windows(self):
        text = self.search.text().strip().casefold()
        matches = [w for w in self._available if text in w.title.casefold() or text in str(w.pid)]
        connected = (self._connected_identity,) if self._connected_identity is not None else ()
        self.window_list.set_windows(matches, connected_identities=connected)
        self.status.setText(f'창 {len(matches)}개 · 선택 후 연결하세요.' if matches else '선택할 창이 없습니다.')

    def _selection_changed(self, target):
        self.confirm_button.setEnabled(target is not None)

    def set_error(self, message):
        self.status.setText(message)

    def accept(self):
        target = self.window_list.selected_window()
        if self.isVisible() and target is not None:
            self.selection_requested.emit(target)

    def finish_selection(self):
        super().accept()
