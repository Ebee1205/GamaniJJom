"""Independent translucent window. All user actions belong to its component."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget

from src.ui.toolbar.toolbar_widget import ToolbarWidget


class ToolbarWindow(QWidget):
    def __init__(self, title: str = "", parent=None):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                 | Qt.WindowType.WindowDoesNotAcceptFocus)
        super().__init__(parent, flags)
        self.log = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle(f"GamaniJJom — {title}")
        self.toolbar = ToolbarWidget(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        self.setFixedSize(self.sizeHint())

    def set_pinned(self, pinned: bool):
        position = self.pos()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, pinned)
        self.move(position)

    def closeEvent(self, event):
        if self.log is not None:
            self.log.debug("TOOLBAR", f">> Toolbar close requested")
        event.ignore()
