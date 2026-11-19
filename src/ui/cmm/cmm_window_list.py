"""Reusable window list. Selection is bound to identity, never to row number."""
from enum import IntEnum

from PySide6.QtCore import Qt, Signal, Property
from PySide6.QtGui import QBrush, QColor, QPainter, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QTreeWidget, QTreeWidgetItem,
    QStyledItemDelegate, QStyleOptionViewItem, QStyle,
)

CONNECTED_ROLE = Qt.ItemDataRole.UserRole + 1
WINDOW_ROLE = Qt.ItemDataRole.UserRole


class Column(IntEnum):
    TITLE = 0
    PID = 1
    HWND = 2
    X = 3
    Y = 4
    WIDTH = 5
    HEIGHT = 6
    STATUS = 7
    OFFSET = 8


HEADERS = ("프로그램 창", "PID", "HWND", "X", "Y", "너비", "높이", "상태", "툴바 오프셋")
DEFAULT_STATUS = "미연결"
DEFAULT_OFFSET = "—"


class _WindowListDelegate(QStyledItemDelegate):
    """Keep a confirmed connection distinct from the current browsing selection."""

    def paint(self, painter, option, index):
        if not index.siblingAtColumn(Column.TITLE).data(CONNECTED_ROLE):
            super().paint(painter, option, index)
            return
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        view = self.parent()
        # The QSS :selected background is reserved for the unconfirmed preview.
        styled.state &= ~QStyle.StateFlag.State_Selected
        background = view.connectedBackground
        if background.isValid():
            styled.backgroundBrush = QBrush(background)
        foreground = view.connectedForeground
        if foreground.isValid():
            styled.palette.setColor(QPalette.ColorRole.Text, foreground)
        view.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, view)


class CmmWindowList(QTreeWidget):
    selection_changed = Signal(object)
    window_activated = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("windowList")
        self.log = None
        self._connected_background = QColor()
        self._connected_foreground = QColor()
        self._empty_text = ""
        self._items = {}  # identity -> QTreeWidgetItem

        self.setItemDelegate(_WindowListDelegate(self))
        self.setHeaderLabels(HEADERS)  # also fixes the column count
        self.setRootIsDecorated(False)
        self.setUniformRowHeights(True)
        self.setAlternatingRowColors(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.header().setSectionResizeMode(Column.TITLE, QHeaderView.ResizeMode.Stretch)

        self.selection_changed.connect(self._log_selection)
        self.itemSelectionChanged.connect(self._emit_selection)
        self.itemDoubleClicked.connect(lambda *_: self.window_activated.emit(self.selected_window()))

    # ---- QSS-styleable properties -------------------------------------------------
    def _get_connected_background(self):
        return self._connected_background

    def _set_connected_background(self, color):
        self._connected_background = QColor(color)
        self.viewport().update()

    def _get_connected_foreground(self):
        return self._connected_foreground

    def _set_connected_foreground(self, color):
        self._connected_foreground = QColor(color)
        self.viewport().update()

    connectedBackground = Property(QColor, _get_connected_background, _set_connected_background)
    connectedForeground = Property(QColor, _get_connected_foreground, _set_connected_foreground)

    # ---- Column configuration -----------------------------------------------------
    def show_only_columns(self, columns):
        """Show just `columns` (Column members); the title column is always kept."""
        visible = {Column.TITLE, *columns}
        for column in Column:
            self.setColumnHidden(column, column not in visible)

    def set_column_title(self, column, text):
        self.headerItem().setText(column, text)

    # ---- Empty state --------------------------------------------------------------
    def set_empty_text(self, text):
        self._empty_text = text
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.topLevelItemCount() or not self._empty_text:
            return
        painter = QPainter(self.viewport())
        painter.setPen(self.palette().color(QPalette.ColorRole.PlaceholderText))
        painter.drawText(self.viewport().rect().adjusted(16, 16, -16, -16),
                         Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self._empty_text)

    # ---- Selection ----------------------------------------------------------------
    def selected_window(self):
        items = self.selectedItems()
        return items[0].data(Column.TITLE, WINDOW_ROLE) if items else None

    def select_identity(self, identity):
        item = self._items.get(identity)
        if item is not None:
            self.setCurrentItem(item)
            self.scrollToItem(item)

    def _emit_selection(self):
        self.selection_changed.emit(self.selected_window())

    def _log_selection(self, target):
        if self.log is None:
            return
        handle = target.handle_text if target else "none"
        pid = target.pid if target else "none"
        self.log.debug("UI", f">> Window selection changed hwnd={handle} pid={pid}")

    # ---- Population ---------------------------------------------------------------
    @staticmethod
    def _make_item(window, status, offset, connected):
        rect = window.rect
        item = QTreeWidgetItem([
            window.title, str(window.pid), window.handle_text,
            str(rect.x), str(rect.y), str(rect.width), str(rect.height),
            status, offset,
        ])
        item.setData(Column.TITLE, WINDOW_ROLE, window)
        item.setData(Column.TITLE, CONNECTED_ROLE, connected)
        item.setToolTip(Column.TITLE,
                        f"{window.title}\nPID {window.pid} · HWND {window.handle_text} · {rect.width}×{rect.height}")
        return item

    def set_windows(self, windows, statuses=None, offsets=None, *, connected_identities=()):
        previous = self.selected_window()
        keep = previous.identity if previous else None
        statuses = statuses or {}
        offsets = offsets or {}
        connected = set(connected_identities)

        self.blockSignals(True)
        try:
            self.clear()
            self._items = {}
            for window in windows:
                identity = window.identity
                item = self._make_item(window,
                                       statuses.get(identity, DEFAULT_STATUS),
                                       offsets.get(identity, DEFAULT_OFFSET),
                                       identity in connected)
                self.addTopLevelItem(item)
                self._items[identity] = item
            for column in range(Column.PID, self.columnCount()):
                self.resizeColumnToContents(column)
            if keep in self._items:
                self.setCurrentItem(self._items[keep])
        finally:
            self.blockSignals(False)
        self.viewport().update()
        self.selection_changed.emit(self.selected_window())