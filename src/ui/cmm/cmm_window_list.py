"""Reusable window list. Selection is bound to identity, never to row number."""
from PySide6.QtCore import Qt, Signal, Property
from PySide6.QtGui import QBrush, QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QTreeWidget, QTreeWidgetItem,
    QStyledItemDelegate, QStyleOptionViewItem, QStyle,
)

CONNECTED_ROLE = Qt.ItemDataRole.UserRole + 1


class _WindowListDelegate(QStyledItemDelegate):
    """Keep a confirmed connection distinct from the current browsing selection."""

    def paint(self, painter, option, index):
        if not index.siblingAtColumn(0).data(CONNECTED_ROLE):
            super().paint(painter, option, index)
            return
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        widget = self.parent()
        # The QSS :selected background is reserved for the unconfirmed preview.
        styled.state &= ~QStyle.StateFlag.State_Selected
        color = widget.connectedBackground
        if color.isValid():
            styled.backgroundBrush = QBrush(color)
        foreground = widget.connectedForeground
        if foreground.isValid():
            styled.palette.setColor(QPalette.ColorRole.Text, foreground)
        widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, widget)


class CmmWindowList(QTreeWidget):
    selection_changed = Signal(object)
    window_activated = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("windowList")
        self._connected_background = QColor()
        self._connected_foreground = QColor()
        self.setItemDelegate(_WindowListDelegate(self))
        self.log = None
        self.selection_changed.connect(lambda target: self.log.debug("UI", f">> Window selection changed hwnd={target.handle_text if target else 'none'} pid={target.pid if target else 'none'}") if self.log is not None else None)
        self.setColumnCount(9)
        self.setHeaderLabels(["프로그램 창", "PID", "HWND", "X", "Y", "너비", "높이", "상태", "툴바 오프셋"])
        self.setRootIsDecorated(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(False)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.itemSelectionChanged.connect(lambda: self.selection_changed.emit(self.selected_window()))
        self.itemDoubleClicked.connect(lambda *_: self.window_activated.emit(self.selected_window()))

    def selected_window(self):
        items = self.selectedItems()
        return items[0].data(0, Qt.ItemDataRole.UserRole) if items else None

    def _set_connected_background(self, color):
        self._connected_background = QColor(color)
        self.viewport().update()

    def _set_connected_foreground(self, color):
        self._connected_foreground = QColor(color)
        self.viewport().update()

    connectedBackground = Property(QColor, lambda self: self._connected_background, _set_connected_background)
    connectedForeground = Property(QColor, lambda self: self._connected_foreground, _set_connected_foreground)

    def set_windows(self, windows, statuses=None, offsets=None, *, connected_identities=()):
        previous = self.selected_window()
        identity = previous.identity if previous else None
        statuses = statuses or {}
        offsets = offsets or {}
        connected = set(connected_identities)
        self.blockSignals(True)
        try:
            self.clear()
            for window in windows:
                rect = window.rect
                item = QTreeWidgetItem([window.title, str(window.pid), window.handle_text,
                                        str(rect.x), str(rect.y), str(rect.width), str(rect.height),
                                        statuses.get(window.identity, "미연결"), offsets.get(window.identity, "—")])
                item.setData(0, Qt.ItemDataRole.UserRole, window)
                item.setData(0, CONNECTED_ROLE, window.identity in connected)
                self.addTopLevelItem(item)
                if window.identity == identity:
                    self.setCurrentItem(item)
            self.resizeColumnToContents(1)
            self.resizeColumnToContents(2)
            for column in range(3, self.columnCount()):
                self.resizeColumnToContents(column)
        finally:
            self.blockSignals(False)
        self.selection_changed.emit(self.selected_window())

    def select_identity(self, identity):
        for index in range(self.topLevelItemCount()):
            item = self.topLevelItem(index)
            if item.data(0, Qt.ItemDataRole.UserRole).identity == identity:
                self.setCurrentItem(item)
                return
