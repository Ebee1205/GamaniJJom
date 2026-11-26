"""Settings popup: category pages containing scrollable child sections."""
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QLayout,
    QPushButton,
    QStackedWidget,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.ui.cmm.cmm_dialog_layout import CmmDialogLayout

DIALOG_SIZE = (760, 520)
DIALOG_MIN_SIZE = (640, 440)
NAV_WIDTH = 190

SECTION_INDEX_ROLE = Qt.ItemDataRole.UserRole    # 트리 항목 -> 섹션 번호
SEARCH_TEXT_ROLE = Qt.ItemDataRole.UserRole + 1  # 트리 항목 -> 검색용 문자열


@dataclass
class _Field:
    """설정 키 하나에 대응하는 입력 위젯과, 읽기/쓰기 방법."""
    widget: QWidget
    get: Callable[[], Any]
    set: Callable[[Any], None]
    initial: Any = None  # 마지막으로 불러오거나 적용한 값 (변경 감지용)


@dataclass
class _Group:
    scroll: QScrollArea
    content: QWidget
    layout: QVBoxLayout


@dataclass
class _Section:
    group: _Group
    widget: QWidget
    breadcrumb: str


class SettingDialog(QDialog):
    """왼쪽 메뉴에서 항목을 고르고, 오른쪽에서 설정하는 대화상자.

    - 값은 [적용]/[확인]을 눌렀을 때만 반영된다. [취소]/X는 변경을 버린다.
    - 반영 시 바뀐 키마다 setting_changed(key, value)가 나가고,
      한꺼번에 받고 싶다면 settings_applied({key: value, ...})를 쓰면 된다.
    """

    setting_changed = Signal(str, object)  # key, value
    settings_applied = Signal(dict)        # {key: value}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.log = None
        self._fields: dict[str, _Field] = {}
        self._sections: list[_Section] = []

        self._setup_window()
        self.surface = CmmDialogLayout(self)
        self.surface.set_title("설정")
        self.surface.close_requested.connect(self.reject)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.surface)

        self._build_body()
        self._build_footer()
        self._build_pages()
        self._refresh_buttons()

    # ------------------------------------------------------------------
    # 창 / 뼈대
    # ------------------------------------------------------------------
    def _setup_window(self):
        self.setObjectName("SettingDialog")
        self.setWindowTitle("GamaniJJom — 설정")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(*DIALOG_SIZE)
        self.setMinimumSize(*DIALOG_MIN_SIZE)

    def _build_body(self):
        """본문: [왼쪽 메뉴 | 오른쪽 페이지]"""
        body = QWidget()
        row = QHBoxLayout(body)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(14)
        row.addWidget(self._build_nav())
        row.addWidget(self._build_content(), 1)
        self.surface.set_body(body)

    def _build_nav(self) -> QWidget:
        """왼쪽: 검색창 + 메뉴 트리."""
        pane = QWidget()
        pane.setFixedWidth(NAV_WIDTH)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.search = QLineEdit()
        self.search.setObjectName("compactField")
        self.search.setPlaceholderText("설정 검색")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_nav)
        layout.addWidget(self.search)

        self.nav = QTreeWidget()
        self.nav.setObjectName("settingNav")
        self.nav.setHeaderHidden(True)
        self.nav.setRootIsDecorated(False)  # 화살표 없이 들여쓰기만 (항상 펼침)
        self.nav.setIndentation(16)
        self.nav.currentItemChanged.connect(self._on_nav_changed)
        self.nav.itemClicked.connect(lambda item, column: self._scroll_to_section(item))
        layout.addWidget(self.nav, 1)
        return pane

    def _build_content(self) -> QWidget:
        """오른쪽: 현재 위치 제목 + 구분선 + 페이지."""
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.page_title = QLabel()
        self.page_title.setObjectName("pageTitle")
        layout.addWidget(self.page_title)

        line = QFrame()
        line.setObjectName("pageLine")
        line.setFixedHeight(1)
        layout.addWidget(line)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        return pane

    def _build_footer(self):
        """푸터: [확인] [취소] [적용]"""
        footer = QWidget()
        row = QHBoxLayout(footer)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addStretch()

        self.ok_button = QPushButton("확인")
        self.ok_button.setObjectName("primaryButton")
        self.ok_button.clicked.connect(self.accept)

        self.cancel_button = QPushButton("취소")
        self.cancel_button.clicked.connect(self.reject)

        self.apply_button = QPushButton("적용")
        self.apply_button.clicked.connect(self.apply)

        for button in (self.ok_button, self.cancel_button, self.apply_button):
            row.addWidget(button)
        self.surface.set_footer(footer)

    # ------------------------------------------------------------------
    # 메뉴 구성 — 항목을 추가하려면 여기에 한 줄과 페이지 메서드 하나만 더하면 된다
    # ------------------------------------------------------------------
    def _build_pages(self):
        save = self._add_page("저장", self._build_save_page())
        self._add_page("파일명", self._build_filename_page(), parent=save)
        self._add_page("캡처 후 동작", self._build_after_capture_page(), parent=save)
        self._add_page("툴바", self._build_toolbar_page())

        self.nav.expandAll()
        self.nav.setCurrentItem(self.nav.topLevelItem(0))

    def _add_page(self, title: str, page: QWidget, parent: QTreeWidgetItem | None = None):
        """상위 항목은 스크롤 페이지, 하위 항목은 같은 페이지의 섹션이다."""
        if parent is None:
            scroll = QScrollArea()
            scroll.setObjectName("settingsScroll")
            scroll.viewport().setObjectName("settingsViewport")
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            content = QWidget()
            content.setObjectName("settingsContent")
            layout = QVBoxLayout(content)
            layout.setContentsMargins(0, 0, 12, 0)
            layout.setSpacing(24)
            layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
            layout.addStretch()
            scroll.setWidget(content)
            self.stack.addWidget(scroll)
            group = _Group(scroll, content, layout)
            breadcrumb = title
        else:
            parent_section = self._sections[parent.data(0, SECTION_INDEX_ROLE)]
            group = parent_section.group
            breadcrumb = f"{parent_section.breadcrumb} › {title}"

        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        heading = QLabel(title if parent is not None else "일반")
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)
        layout.addWidget(page)
        group.layout.insertWidget(group.layout.count()-1, section)

        index = len(self._sections)
        self._sections.append(_Section(group, section, breadcrumb))
        item = QTreeWidgetItem(parent or self.nav, [title])
        item.setData(0, SECTION_INDEX_ROLE, index)
        item.setData(0, SEARCH_TEXT_ROLE, self._search_text(title, page))
        return item

    @staticmethod
    def _search_text(title: str, page: QWidget) -> str:
        """검색에 쓸 문자열: 제목 + 페이지 안의 라벨/체크박스 글자."""
        texts = [title]
        texts += [w.text() for w in page.findChildren(QLabel)]
        texts += [w.text() for w in page.findChildren(QCheckBox)]
        return " ".join(texts).lower()

    # ------------------------------------------------------------------
    # 페이지들
    # ------------------------------------------------------------------
    def _build_save_page(self) -> QWidget:
        page, form = self._new_page()
        form.addRow("저장 경로", self._path_row())
        form.addRow("이미지 배율", self._combo_field(
            "save.scale", [("1배", 1), ("2배", 2), ("3배", 3)]))
        return page

    def _build_filename_page(self) -> QWidget:
        page, form = self._new_page()
        form.addRow("파일명 접두어", self._text_field("save.filename.prefix"))
        form.addRow(self._check_field("save.filename.postfix_date_enabled", "파일명에 날짜 포함"))
        return page

    def _build_after_capture_page(self) -> QWidget:
        page, form = self._new_page()
        form.addRow(self._check_field("save.notification_enabled", "캡처 완료 알림 표시"))
        form.addRow(self._check_field("save.copy_to_clipboard", "클립보드에 자동 복사"))
        return page

    def _build_toolbar_page(self) -> QWidget:
        page, form = self._new_page()
        form.addRow("툴바 테마", self._combo_field(
            "theme", [("원형", "circle"), ("사각형", "square")]))
        return page

    @staticmethod
    def _new_page() -> tuple[QWidget, QFormLayout]:
        """위쪽 정렬 폼 하나를 가진 빈 페이지."""
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 4, 0, 0)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        outer.addLayout(form)
        return page, form

    # ------------------------------------------------------------------
    # 입력 위젯 (만들면서 키와 함께 등록한다)
    # ------------------------------------------------------------------
    def _register(self, key, widget, get, set_, changed_signal):
        self._fields[key] = _Field(widget, get, set_)
        changed_signal.connect(self._refresh_buttons)

    def _text_field(self, key: str) -> QLineEdit:
        edit = QLineEdit()
        self._register(key, edit, edit.text, edit.setText, edit.textChanged)
        return edit

    def _check_field(self, key: str, text: str) -> QCheckBox:
        box = QCheckBox(text)
        self._register(key, box, box.isChecked, box.setChecked, box.toggled)
        return box

    def _combo_field(self, key: str, options: list[tuple[str, Any]]) -> QComboBox:
        """(표시 글자, 실제 값) 목록으로 콤보박스를 만든다."""
        combo = QComboBox()
        for label, value in options:
            combo.addItem(label, value)

        def set_value(value):
            index = combo.findData(value)
            if index >= 0:
                combo.setCurrentIndex(index)

        self._register(key, combo, combo.currentData, set_value, combo.currentIndexChanged)
        return combo

    def _path_row(self) -> QWidget:
        """저장 경로 입력 + [찾아보기…]"""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.path_edit = self._text_field("save.path")
        browse = QPushButton("찾아보기…")
        browse.clicked.connect(self._on_browse_save_path)
        layout.addWidget(self.path_edit, 1)
        layout.addWidget(browse)
        return row

    # ------------------------------------------------------------------
    # 메뉴 이동 / 검색
    # ------------------------------------------------------------------
    def _on_nav_changed(self, current: QTreeWidgetItem | None, _previous):
        if current is None:
            return
        index = current.data(0, SECTION_INDEX_ROLE)
        section = self._sections[index]
        self.stack.setCurrentWidget(section.group.scroll)
        self.page_title.setText(section.breadcrumb)
        self._debug(f">> Settings section selected index={index}")
        # Wait for the selected category's scroll range and layout to update.
        QTimer.singleShot(0, lambda: self._scroll_to_section(current))

    def _scroll_to_section(self, item):
        if self.nav.currentItem() is not item:
            return
        index = item.data(0, SECTION_INDEX_ROLE)
        section = self._sections[index]
        section.group.layout.activate()
        position = 0 if item.parent() is None else section.widget.y()
        bar = section.group.scroll.verticalScrollBar()
        bar.setValue(position)
        self._debug(f"<< Settings section revealed index={index} scroll={bar.value()}")

    def _filter_nav(self, text: str):
        needle = text.strip().lower()
        for i in range(self.nav.topLevelItemCount()):
            self._apply_filter(self.nav.topLevelItem(i), needle)

    def _apply_filter(self, item: QTreeWidgetItem, needle: str) -> bool:
        """자신이나 자식이 검색어와 맞으면 보이게 한다. 보이면 True."""
        child_visible = False
        for i in range(item.childCount()):
            if self._apply_filter(item.child(i), needle):
                child_visible = True
        matches = not needle or needle in item.data(0, SEARCH_TEXT_ROLE)
        visible = matches or child_visible
        item.setHidden(not visible)
        return visible

    # ------------------------------------------------------------------
    # 값 불러오기 / 적용
    # ------------------------------------------------------------------
    def load_config(self, config):
        """설정값을 UI에 채우고, 이 시점을 '변경 없음' 기준으로 삼는다."""
        if config is None:
            return
        for key, field in self._fields.items():
            field.set(self._resolve(config, key))
            field.initial = field.get()
        self._refresh_buttons()

    @staticmethod
    def _resolve(config, dotted_key: str):
        """config.save.filename.prefix 처럼 점(.) 경로로 값을 꺼낸다."""
        value = config
        for part in dotted_key.split("."):
            value = getattr(value, part)
        return value

    def changed_values(self) -> dict[str, Any]:
        """마지막 적용 이후 바뀐 값들."""
        return {
            key: field.get()
            for key, field in self._fields.items()
            if field.get() != field.initial
        }

    def apply(self):
        """바뀐 값을 반영한다 (대화상자는 닫지 않음)."""
        changes = self.changed_values()
        if not changes:
            return True
        for key, value in changes.items():
            self.setting_changed.emit(key, value)
        self.settings_applied.emit(changes)
        self._refresh_buttons()
        success = not self.changed_values()
        self._debug(f"<< Settings apply completed count={len(changes)} result={'saved' if success else 'pending'}")
        return success

    def mark_applied(self, changes):
        """Advance the change baseline only after the controller confirms saving."""
        for key, value in changes.items():
            self._fields[key].initial = value
        self._refresh_buttons()

    def accept(self):
        if self.apply():
            super().accept()

    def _refresh_buttons(self, *_):
        """바뀐 값이 있을 때만 [적용]을 켠다."""
        self.apply_button.setEnabled(bool(self.changed_values()))

    # ------------------------------------------------------------------
    # 기타
    # ------------------------------------------------------------------
    def _on_browse_save_path(self):
        """저장 경로 선택 대화상자를 연다."""
        try:
            initial_dir = str(Path(self.path_edit.text()).resolve())
        except Exception:
            initial_dir = str(Path.home())

        selected = QFileDialog.getExistingDirectory(
            self, "저장 경로 선택", initial_dir, QFileDialog.Option.ShowDirsOnly
        )
        if not selected:
            return

        path = Path(selected).as_posix()  # 슬래시로 통일
        if not path.endswith("/"):
            path += "/"
        self.path_edit.setText(path)
        self._debug(f">> Save path selected {path}")

    def showEvent(self, event):
        self._debug("<< Settings dialog displayed")
        super().showEvent(event)

    def done(self, result):
        self._debug(f">> Settings dialog dismissed result={result}")
        super().done(result)

    def _debug(self, message: str):
        if self.log is not None:
            self.log.debug("SETTINGS", message)
