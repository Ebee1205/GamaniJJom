"""필요할 때 여는 PySide6 대상 선택·좌표 편집 창."""
from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QAbstractItemView,
)

from src.models.window_schema import WindowInfo, WindowRect
from src.services.window_service import WindowService
from src.services.window_service import _validate_rect


class MainWindow(QDialog):
    """On-demand picker/editor. Closing it leaves the tray running."""
    target_chosen = Signal(object)
    geometry_requested = Signal(object)
    geometry_applied = Signal(object)

    def __init__(self, service: WindowService):
        super().__init__()
        self.service = service
        self.windows: list[WindowInfo] = []
        self.selected: WindowInfo | None = None
        self._busy = False
        self.setWindowTitle("GamaniJJom — 프로그램 연결")
        self.resize(850, 380)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["HWND", "PID", "제목", "X", "Y", "너비", "높이"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.on_select)
        self.table.doubleClicked.connect(self.choose)
        layout.addWidget(self.table)
        editor = QHBoxLayout()
        self.inputs = {}
        for name, label in (("x", "X"), ("y", "Y"), ("width", "너비"), ("height", "높이")):
            editor.addWidget(QLabel(label))
            field = QLineEdit()
            field.setMaximumWidth(90)
            self.inputs[name] = field
            editor.addWidget(field)
        self.apply_button = QPushButton("위치·크기 적용")
        self.apply_button.clicked.connect(self.apply)
        editor.addWidget(self.apply_button)
        layout.addLayout(editor)
        actions = QHBoxLayout()
        refresh = QPushButton("새로고침 (F5)")
        refresh.clicked.connect(self.refresh)
        actions.addWidget(refresh)
        self.attach_button = QPushButton("선택한 창 연결")
        self.attach_button.clicked.connect(self.choose)
        actions.addWidget(self.attach_button)
        close = QPushButton("닫기")
        close.clicked.connect(self.hide)
        actions.addWidget(close)
        layout.addLayout(actions)
        self.status = QLabel("일반 창으로 복원한 뒤 좌표를 적용하세요. 단위: 화면 픽셀")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        self.refresh_shortcut.activated.connect(self.refresh)
        self.on_select()

    def refresh(self):
        previous = self.selected.identity if self.selected else None
        try:
            windows = self.service.list_windows()
        except OSError as error:
            self.status.setText(str(error))
            return
        self.table.blockSignals(True)
        self.windows = windows
        self.table.setRowCount(len(windows))
        for row, info in enumerate(windows):
            r = info.rect
            for col, value in enumerate((info.handle_text, info.pid, info.title,
                                         r.x, r.y, r.width, r.height)):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
        self.table.clearSelection()
        self.table.blockSignals(False)
        for row, info in enumerate(windows):
            if info.identity == previous:
                self.table.selectRow(row)
                break
        self.table.resizeColumnsToContents()
        self.on_select()
        self.status.setText(f"창 {len(windows)}개 · 연결 후 대상 창을 활성화하면 툴바가 표시됩니다.")

    def on_select(self):
        row = self.table.currentRow()
        self.selected = None
        if self.table.selectedItems() and 0 <= row < len(self.windows):
            try:
                self.selected = self.service.read(self.windows[row])
            except OSError as error:
                self.status.setText(str(error))
        for name, field in self.inputs.items():
            field.setText(str(getattr(self.selected.rect, name)) if self.selected else "")
        self.apply_button.setEnabled(self.selected is not None and not self._busy)
        self.attach_button.setEnabled(self.selected is not None)

    def choose(self, *_):
        if self.selected:
            self.target_chosen.emit(self.selected)

    def apply(self):
        target = self.selected
        if not target or self._busy:
            return
        try:
            rect = WindowRect(*(int(field.text()) for field in self.inputs.values()))
            _validate_rect(rect)
            self.geometry_requested.emit(target)
            self.service.apply(target, rect)
        except (ValueError, OSError) as error:
            self.status.setText(f"적용 실패: {error}")
            return
        self._busy = True
        self.apply_button.setEnabled(False)
        self.status.setText("변경 요청을 보냈습니다. 실제 결과 확인 중…")
        QTimer.singleShot(300, lambda: self.verify(target, rect))

    def verify(self, target, requested):
        self._busy = False
        try:
            current = self.service.read(target)
        except OSError as error:
            self.status.setText(f"결과 확인 실패: {error}")
        else:
            self.geometry_applied.emit(current)
            if self.selected and self.selected.identity == current.identity:
                self.selected = current
                for name, field in self.inputs.items():
                    field.setText(str(getattr(current.rect, name)))
            self.status.setText("위치·크기 적용 완료" if current.rect == requested else
                                "요청과 실제 결과가 다릅니다. 대상 앱의 크기 제한·권한을 확인하세요.")
        self.apply_button.setEnabled(self.selected is not None)

    def closeEvent(self, event):
        self.hide()
        event.ignore()
