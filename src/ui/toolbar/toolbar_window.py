"""Independent translucent window. All user actions belong to its component."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QWidget


from src.ui.toolbar.toolbar_widget import ToolbarWidget


class ToolbarWindow(QWidget):
    def __init__(self, title: str = "", parent=None):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                 | Qt.WindowType.WindowDoesNotAcceptFocus)
        super().__init__(parent, flags)
        self.log = None
        self._closing = False
        self._candidate = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle(f"GamaniJJom — {title}")
        self.toolbar = ToolbarWidget(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        self.setFixedSize(self.sizeHint())

    def show_candidate(self, rect):
        if rect is None:
            if self._candidate is not None:
                self._candidate.hide()
            return
        if self._candidate is None:
            flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                     | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus
                     | Qt.WindowType.WindowTransparentForInput)
            self._candidate = QFrame(None, flags)
            self._candidate.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self._candidate.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            self._candidate.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self._candidate.setStyleSheet("QFrame { border: 3px solid #75d8bf; background: transparent; }")
        self._candidate.show()
        return int(self._candidate.winId())

    def dispose(self):
        self._closing = True
        if self._candidate is not None:
            self._candidate.close()
            self._candidate.deleteLater()
        self.close()

    def closeEvent(self, event):
        if self._closing:
            event.accept()
        else:
            event.ignore()
