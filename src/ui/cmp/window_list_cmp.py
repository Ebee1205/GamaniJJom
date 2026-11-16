"""Reusable window list. Selection is bound to identity, never to row number."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTreeWidget, QTreeWidgetItem


class WindowListComponent(QTreeWidget):
    selection_changed = Signal(object)
    window_activated = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.log = None
        self.selection_changed.connect(lambda target: self.log.debug("UI", f">> Window selection changed hwnd={target.handle_text if target else 'none'} pid={target.pid if target else 'none'}") if self.log is not None else None)
        self.setColumnCount(4)
        self.setHeaderLabels(["프로그램 창", "PID", "HWND", "상태"])
        self.setRootIsDecorated(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(False)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.itemSelectionChanged.connect(lambda: self.selection_changed.emit(self.selected_window()))
        self.itemDoubleClicked.connect(lambda *_: self.window_activated.emit(self.selected_window()))

    def selected_window(self):
        items = self.selectedItems()
        return items[0].data(0, Qt.ItemDataRole.UserRole) if items else None

    def set_windows(self, windows, statuses=None):
        previous = self.selected_window()
        identity = previous.identity if previous else None
        statuses = statuses or {}
        self.blockSignals(True)
        try:
            self.clear()
            for window in windows:
                item = QTreeWidgetItem([window.title, str(window.pid), window.handle_text,
                                        statuses.get(window.identity, "선택 가능")])
                item.setData(0, Qt.ItemDataRole.UserRole, window)
                self.addTopLevelItem(item)
                if window.identity == identity:
                    self.setCurrentItem(item)
            self.resizeColumnToContents(1)
            self.resizeColumnToContents(2)
        finally:
            self.blockSignals(False)
        self.selection_changed.emit(self.selected_window())

    def select_identity(self, identity):
        for index in range(self.topLevelItemCount()):
            item = self.topLevelItem(index)
            if item.data(0, Qt.ItemDataRole.UserRole).identity == identity:
                self.setCurrentItem(item)
                return
