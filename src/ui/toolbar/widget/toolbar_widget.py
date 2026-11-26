"""Independent translucent toolbar window.

Collapse, expand and drag are built in and theme-independent. The cover is the
main face; the inner menu appears when the cover is expanded. Both are drawn by
the active ToolbarTheme ('circle' by default), which can be swapped at runtime:

    widget.set_theme('square')

or injected from QSS (theme.qss), no code change needed:

    QWidget#toolbarWindow { qproperty-toolbarTheme: "square"; }
"""
from PySide6.QtCore import Property, Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QWidget

from src.adapters.windows import window_api
from src.ui.cmm.cmm_window_flags import TOOLBAR_WINDOW_FLAGS
from src.ui.cmm.cmm_window_overlay import CmmWindowOverlay
from src.ui.resources import app_icon
from src.ui.toolbar.widget import themes  # noqa: F401  (registers the built-in themes)
from src.ui.toolbar.widget.toolbar_cover_widget import ToolbarCoverWidget
from src.ui.toolbar.widget.toolbar_theme import THEME_ALIASES, ToolbarTheme, create_theme

DEFAULT_THEME = 'square'


class ToolbarWidget(QWidget):
    def __init__(self, title: str = '', parent=None, *, theme=None, mode=None):
        super().__init__(parent, TOOLBAR_WINDOW_FLAGS)
        self.log = None
        self._closing = False
        self._taskbar_enabled = False
        self._taskbar_hwnd = None
        self._candidate = None
        self.setObjectName('toolbarWindow')
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle(f'GamaniJJom — {title}')
        self.setWindowIcon(app_icon())

        self._theme = create_theme(DEFAULT_THEME)
        self.toolbar = ToolbarCoverWidget(self._theme, self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        self.setFixedSize(self.sizeHint())
        self.apply_shape()

        # Apply QSS first so a theme chosen in code (theme= / legacy mode=) wins over it.
        self.ensurePolished()
        explicit = theme if theme is not None else mode
        if explicit is not None:
            self.set_theme(explicit)

    # ---- Theme -----------------------------------------------------------------------
    @property
    def theme(self) -> ToolbarTheme:
        return self._theme

    @property
    def mode(self) -> str:
        """Name of the active theme (the old renderer 'mode')."""
        return self._theme.name

    def set_theme(self, theme):
        """Switch theme by registered name or ToolbarTheme instance."""
        if isinstance(theme, str):
            if THEME_ALIASES.get(theme, theme) == self._theme.name:
                return
            theme = create_theme(theme)
        self.toolbar.collapse()
        self.toolbar.cancel_drag()
        self._theme = theme
        self.toolbar.set_theme(theme)
        self.layout().invalidate()
        self.setFixedSize(self.toolbar.sizeHint())
        self.apply_shape()

    set_mode = set_theme   # old name

    # Qt property so a stylesheet can pick the theme (qproperty-toolbarTheme).
    toolbarTheme = Property(str, lambda self: self._theme.name, set_theme)

    def apply_shape(self):
        mask = self._theme.cover_mask(self.toolbar.dock)
        if mask is None:
            self.clearMask()
        else:
            self.setMask(mask)

    # ---- Built-in behaviour (forwarded from the cover) -------------------------------
    @property
    def is_expanded(self):
        return self.toolbar.is_expanded

    def expand(self):
        self.toolbar.expand()

    def collapse(self):
        self.toolbar.collapse()

    def cancel_drag(self):
        self.toolbar.cancel_drag()

    # ---- Window ----------------------------------------------------------------------
    def set_taskbar_enabled(self, enabled: bool):
        self._taskbar_enabled = enabled
        self._sync_taskbar()

    def _sync_taskbar(self):
        if self._closing or not self._taskbar_enabled or not self.isVisible():
            self._remove_taskbar()
            return
        hwnd = int(self.winId())
        if self._taskbar_hwnd == hwnd:
            return
        self._remove_taskbar()
        try:
            window_api.set_taskbar_visible(hwnd, True)
        except OSError as error:
            if self.log is not None:
                self.log.warning("TASKBAR", str(error))
        else:
            self._taskbar_hwnd = hwnd

    def _remove_taskbar(self):
        hwnd = self._taskbar_hwnd
        if hwnd is None:
            return
        self._taskbar_hwnd = None
        try:
            window_api.set_taskbar_visible(hwnd, False)
        except OSError as error:
            if self.log is not None:
                self.log.warning("TASKBAR", str(error))

    def showEvent(self, event):
        super().showEvent(event)
        # Qt's show event may precede actual native visibility.
        QTimer.singleShot(0, self._sync_taskbar)

    def hideEvent(self, event):
        self._remove_taskbar()
        super().hideEvent(event)

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
            self._candidate = CmmWindowOverlay()
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
        self._remove_taskbar()
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
