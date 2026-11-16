"""Independent translucent window. All user actions belong to its component."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget

from src.ui.cmp.toolbar_cmp import ToolbarComponent


class FloatingToolbarWindow(QWidget):
    def __init__(self, title: str = "", parent=None):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                 | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        super().__init__(parent, flags)
        self.log = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle(f"GamaniJJom — {title}")
        self.toolbar = ToolbarComponent(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        self.setFixedSize(self.sizeHint())

    def closeEvent(self, event):
        if self.log is not None:
            self.log.debug("TOOLBAR", f">> Toolbar close requested")
        self.toolbar.hide_requested.emit()
        event.ignore()
