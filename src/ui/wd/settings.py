"""Unified debug screen for available and attached program windows."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.ui.cmp.window_list_cmp import WindowListComponent

# --- 화면 크기 / 여백 ---------------------------------------------------
WINDOW_SIZE = (1120, 720)
WINDOW_MIN_SIZE = (860, 560)
WINDOW_MARGINS = (20, 18, 20, 18)
SPLITTER_SIZES = [340, 260]  # [연결 가능 목록, 연결된 목록]

# --- 화면에 표시되는 문구 -------------------------------------------------
TEXT_WINDOW_TITLE = "GamaniJJom — 프로그램 목록"
TEXT_ALL_TITLE = "프로그램 전체 목록"
TEXT_CONNECTED_TITLE = "현재 연결된 프로그램 목록"
TEXT_EMPTY_COUNT = "0개"
TEXT_REFRESH = "새로고침 · F5"
TEXT_CONNECT = "선택한 프로그램 연결/변경"
TEXT_STATUS = "프로그램 1개에 컨트롤러를 계속 표시합니다. 연결/변경 버튼으로 대상을 바꾸세요."


class SettingsWindow(QWidget):
    """연결 가능한 프로그램 목록과, 현재 연결된 프로그램 목록을 한 화면에 보여준다."""

    target_requested = Signal(object)    # 연결/변경할 프로그램을 선택함
    refresh_requested = Signal()         # 목록 새로고침 요청
    quit_requested = Signal()            # 창 닫힘
    reveal_requested = Signal(object)    # 컨트롤러 표시 요청
    position_requested = Signal(object)  # 위치·크기 변경 요청

    def __init__(self, parent=None):
        super().__init__(parent)
        self.log = None
        self.exit_confirmed = False

        self._setup_window()

        root = QVBoxLayout(self)
        root.setContentsMargins(*WINDOW_MARGINS)
        root.addLayout(self._build_header())
        root.addWidget(self._build_splitter())
        root.addWidget(self._build_status_label())

        self._connect_signals()
        self._setup_shortcuts()

    # ------------------------------------------------------------------
    # UI 구성
    # ------------------------------------------------------------------
    def _setup_window(self):
        self.setObjectName("settingsWindow")
        self.setWindowTitle(TEXT_WINDOW_TITLE)
        self.resize(*WINDOW_SIZE)
        self.setMinimumSize(*WINDOW_MIN_SIZE)

    def _build_header(self):
        """상단 제목 + 전체 프로그램 개수."""
        self.all_count = QLabel(TEXT_EMPTY_COUNT)
        return self._make_title_row(TEXT_ALL_TITLE, self.all_count)

    def _build_splitter(self):
        """위: 연결 가능한 목록 / 아래: 연결된 목록."""
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._build_available_section())
        splitter.addWidget(self._build_attached_section())
        splitter.setChildrenCollapsible(False)
        splitter.setSizes(SPLITTER_SIZES)
        return splitter

    def _build_available_section(self):
        """연결 가능한 프로그램 목록과 [새로고침], [연결/변경] 버튼."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)

        self.available_list = WindowListComponent()
        layout.addWidget(self.available_list)

        refresh_button = QPushButton(TEXT_REFRESH)
        refresh_button.clicked.connect(self.refresh_requested.emit)

        self.connect_button = QPushButton(TEXT_CONNECT)
        self.connect_button.setObjectName("primaryButton")
        self.connect_button.setEnabled(False)  # 선택 전에는 비활성화
        self.connect_button.clicked.connect(self.connect_selected)

        buttons = QHBoxLayout()
        buttons.addWidget(refresh_button)
        buttons.addStretch()
        buttons.addWidget(self.connect_button)
        layout.addLayout(buttons)
        return section

    def _build_attached_section(self):
        """현재 연결된 프로그램 목록과 [컨트롤러 표시], [위치·크기] 버튼."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 10, 0, 0)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(separator)

        self.connected_count = QLabel(TEXT_EMPTY_COUNT)
        layout.addLayout(self._make_title_row(TEXT_CONNECTED_TITLE, self.connected_count))

        self.window_list = WindowListComponent()
        layout.addWidget(self.window_list)
        layout.addLayout(self._build_attached_actions())
        return section

    def _build_attached_actions(self):
        """선택한 연결 프로그램에 적용하는 버튼들 (선택 전에는 비활성화)."""
        action_specs = (
            ("컨트롤러 표시", self.reveal_requested),
            ("위치·크기…", self.position_requested),
        )
        layout = QHBoxLayout()
        self.actions = []
        for text, signal in action_specs:
            button = QPushButton(text)
            button.setEnabled(False)
            button.clicked.connect(lambda checked=False, s=signal: self.emit_selected(s))
            self.actions.append(button)
            layout.addWidget(button)
        layout.addStretch()
        return layout

    def _build_status_label(self):
        self.status = QLabel(TEXT_STATUS)
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        return self.status

    @staticmethod
    def _make_title_row(title_text, count_label):
        """'제목 ........ N개' 형태의 한 줄을 만든다."""
        title = QLabel(title_text)
        title.setObjectName("heading")

        row = QHBoxLayout()
        row.addWidget(title)
        row.addStretch()
        row.addWidget(count_label)
        return row

    # ------------------------------------------------------------------
    # 시그널 / 단축키
    # ------------------------------------------------------------------
    def _connect_signals(self):
        # 연결된 목록에서 선택이 바뀌면 하단 버튼 활성화 상태 갱신
        self.window_list.selection_changed.connect(self.update_actions)
        # 연결 가능 목록에서 선택이 있어야만 [연결/변경] 버튼 활성화
        self.available_list.selection_changed.connect(
            lambda target: self.connect_button.setEnabled(target is not None)
        )
        # 더블클릭(활성화) 시 바로 연결
        self.available_list.window_activated.connect(lambda _: self.connect_selected())

    def _setup_shortcuts(self):
        self.refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        self.refresh_shortcut.activated.connect(self.refresh_requested.emit)

    # ------------------------------------------------------------------
    # 동작
    # ------------------------------------------------------------------
    def connect_selected(self):
        """연결 가능 목록에서 선택한 프로그램으로 연결/변경을 요청한다."""
        target = self.available_list.selected_window()
        if target is None:
            return
        self._debug("UI", f">> Program connection selected hwnd={target.handle_text} pid={target.pid}")
        self.target_requested.emit(target)

    def update_actions(self, target):
        """연결된 프로그램이 선택된 경우에만 하단 버튼을 활성화한다."""
        for button in self.actions:
            button.setEnabled(target is not None)

    def emit_selected(self, signal):
        """연결된 목록에서 선택한 프로그램을 인자로 시그널을 보낸다."""
        self._debug("SETTINGS", ">> Selected window action requested")
        target = self.window_list.selected_window()
        if target is not None:
            signal.emit(target)

    def closeEvent(self, event):
        if self.exit_confirmed:
            event.accept()
            return
        self._debug("UI", ">> Main window close requested")
        event.ignore()
        self.quit_requested.emit()

    def _debug(self, tag, message):
        """로거가 설정되어 있을 때만 디버그 로그를 남긴다."""
        if self.log is not None:
            self.log.debug(tag, message)
