"""Independent translucent window. All user actions belong to its component."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QRegion
from PySide6.QtWidgets import QHBoxLayout, QWidget

from src.ui.toolbar.toolbar_widget import ToolbarWidget
from src.ui.toolbar.window_highlight_overlay import WindowHighlightOverlay
from src.ui.toolbar.circle_toolbar_widget import CircleToolbarWidget


class ToolbarWindow(QWidget):
    def __init__(self, title: str = "", parent=None, *, mode='circle'):
        if mode not in ('circle', 'bar'):
            raise ValueError('Unknown toolbar renderer')
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                 | Qt.WindowType.WindowDoesNotAcceptFocus)
        super().__init__(parent, flags)
        self.log = None
        self._closing = False
        self._candidate = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle(f"GamaniJJom — {title}")
        self.mode = mode
        self.toolbar = CircleToolbarWidget(self) if mode == 'circle' else ToolbarWidget(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        self.setFixedSize(self.sizeHint())
        self._apply_shape()

    def _apply_shape(self):
        if self.mode == 'circle':
            from PySide6.QtCore import QRect
            region = QRegion(0, 0, 60, 60, QRegion.RegionType.Ellipse)
            dock = getattr(self.toolbar, 'dock', None)
            if dock:
                clips = {'right': QRect(30, 0, 30, 60), 'left': QRect(0, 0, 30, 60),
                         'top': QRect(0, 0, 60, 30), 'bottom': QRect(0, 30, 60, 30)}
                region = region.intersected(QRegion(clips[dock]))
            self.setMask(region)
        else:
            self.clearMask()

    def set_mode(self, mode):
        if mode not in ('circle', 'bar'):
            raise ValueError('Unknown toolbar renderer')
        if mode == self.mode:
            return
        old = self.toolbar
        old.blockSignals(True)
        old.menu.hide()
        old.handle.cancel_drag()
        if hasattr(old, 'dispose'):
            old.dispose()
        self.layout().removeWidget(old)
        old.hide()
        old.deleteLater()
        self.mode = mode
        self.toolbar = CircleToolbarWidget(self) if mode == 'circle' else ToolbarWidget(self)
        self.layout().addWidget(self.toolbar)
        self.toolbar.ensurePolished()
        self.toolbar.show()
        self.layout().invalidate()
        self.setFixedSize(self.toolbar.sizeHint())
        self._apply_shape()

    def ensure_visible(self):
        # show() preserves WindowMinimized, leaving an apparently visible QWidget
        # at native minimized coordinates. Restore only this toolbar window.
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()

    def show_candidate(self, rect, *, selection=False):
        if rect is None:
            if self._candidate is not None:
                self._candidate.hide()
            return
        if self._candidate is None:
            self._candidate = WindowHighlightOverlay()
        self._candidate.set_selection(selection)
        self._candidate.show()
        return int(self._candidate.winId())

    @property
    def candidate_handle(self):
        return int(self._candidate.winId()) if self._candidate is not None else None

    def dispose(self):
        if self._closing:
            return
        self._closing = True
        if hasattr(self.toolbar, 'dispose'):
            self.toolbar.dispose()
        if self._candidate is not None:
            self._candidate.close()
            self._candidate.deleteLater()
        self.close()

    def closeEvent(self, event):
        if self._closing:
            event.accept()
        else:
            event.ignore()
