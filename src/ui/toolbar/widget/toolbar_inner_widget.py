"""The menu that appears when the cover is expanded (right-button marking menu).

Selection and tracking live here; where slots are and how they look comes from
the active theme's SlotLayout.
"""
import time

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget
from shiboken6 import isValid

from src.models.toolbar_tool_schema import TOOLBAR_TOOLS
from src.ui.toolbar.widget.themes.theme_circle import layout_angles, slot_at  # noqa: F401  (kept for existing imports)
from src.ui.toolbar.widget.toolbar_theme import ZONE_DEAD, ZONE_PRIMARY

OPEN_DURATION = .13


class ToolbarInnerWidget(QWidget):
    opened = Signal()
    closed = Signal()

    def __init__(self, toolbar):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.NoDropShadowWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.toolbar = toolbar
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.tools = TOOLBAR_TOOLS
        self.slots = None            # SlotLayout while expanded
        self.selected = None
        self.child_selected = None
        self.progress = 1.0          # open animation, 0..1
        self._right_tracking = False
        self._opened_at = 0.0
        self._animation = QTimer(self)
        self._animation.setInterval(16)
        self._animation.timeout.connect(self.update)

    # ---- State shortcuts ------------------------------------------------------------
    @property
    def theme(self):
        return self.toolbar.theme

    @property
    def center(self):
        return self.slots.center if self.slots else QPointF()

    @property
    def submenu_parent(self):
        return self.slots.submenu_parent if self.slots else None

    @property
    def submenu_tools(self):
        return self.slots.child_tools if self.slots else ()

    # ---- Expand / collapse ----------------------------------------------------------
    def open_ring(self, global_center, *, right_tracking=False):
        if self.isVisible():
            self.close_menu()
            return
        anchor = global_center.toPoint() if isinstance(global_center, QPointF) else global_center
        screen = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
        self.slots = self.theme.create_layout(self.tools, self.toolbar.dock, anchor, screen.availableGeometry())
        self.setFixedSize(self.slots.size)
        self.toolbar.more_menu.hide()
        self.selected = self.child_selected = None
        self._right_tracking = right_tracking
        self._opened_at = time.monotonic()
        # Keep the menu centred on the cover, including near screen edges.
        self.move(self.slots.window_origin(anchor))
        self.show()
        self.setFocus(Qt.FocusReason.PopupFocusReason)
        self.grabMouse()
        self.grabKeyboard()
        self._animation.start()
        self.update()
        self.opened.emit()

    def close_menu(self):
        self._right_tracking = False
        self.hide()

    def hideEvent(self, event):
        self._animation.stop()
        self._right_tracking = False
        self.slots = None
        self.selected = self.child_selected = None
        if self.mouseGrabber() is self:
            self.releaseMouse()
        if self.keyboardGrabber() is self:
            self.releaseKeyboard()
        if isValid(self.toolbar):
            self.toolbar.update()
        super().hideEvent(event)
        self.closed.emit()

    def _open_submenu(self, index):
        if self.slots.submenu_parent == index:
            return
        anchor = self.mapToGlobal(self.slots.center.toPoint())
        if self.slots.open_submenu(index):   # the layout needs a bigger window
            self.setFixedSize(self.slots.size)
            self.move(self.slots.window_origin(anchor))
        self.selected = index
        self.child_selected = None
        if self.mouseGrabber() is not self:
            self.grabMouse()
        self.update()

    # ---- Tracking -------------------------------------------------------------------
    def _track(self, global_point):
        slots = self.slots
        point = QPointF(self.mapFromGlobal(global_point.toPoint()))
        zone = slots.zone(point)
        if zone == ZONE_DEAD:
            self.selected = self.child_selected = None
            slots.close_submenu()
        elif zone == ZONE_PRIMARY or slots.submenu_parent is None:
            index = slots.slot_at(point, self.selected)
            self.selected = index
            if index is not None and self.tools[index].children:
                self._open_submenu(index)
            else:
                slots.close_submenu()
                self.child_selected = None
        # The window may have moved while opening a submenu.
        point = QPointF(self.mapFromGlobal(global_point.toPoint()))
        self.child_selected = slots.child_at(point)
        self.update()

    def _execute(self, tool):
        if not self.toolbar.tool_enabled(tool.id):
            self.close_menu()
            return
        if self.toolbar.log is not None:
            self.toolbar.log.debug('TOOLBAR', f'Radial action selected id={tool.id}')
        self.close_menu()
        self.toolbar.activate_tool(tool.id)

    def choose(self, index):
        if index is None or not 0 <= index < len(self.tools):
            self.close_menu()
        elif self.tools[index].children:
            self._open_submenu(index)
        else:
            self._execute(self.tools[index])

    # ---- Events ---------------------------------------------------------------------
    def mouseMoveEvent(self, event):
        if self._right_tracking and self.slots is not None:
            self._track(event.globalPosition())
        event.accept()

    def mousePressEvent(self, event):
        # The marking menu has no second click-selection phase.
        self.close_menu()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton and self._right_tracking and self.slots is not None:
            self._track(event.globalPosition())
            tool = (self.submenu_tools[self.child_selected]
                    if self.submenu_tools and self.child_selected is not None
                    else self.tools[self.selected]
                    if self.selected is not None and (not self.tools[self.selected].children
                                                      or self.tools[self.selected].kind in ('action', 'toggle'))
                    else None)
            if tool is None:
                self.close_menu()
            else:
                self._execute(tool)
        else:
            self.close_menu()
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close_menu()
            event.accept()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        if self.slots is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        elapsed = min(1.0, (time.monotonic() - self._opened_at) / OPEN_DURATION)
        self.progress = 1 - (1 - elapsed) ** 3
        if elapsed >= 1:
            self._animation.stop()
        self.theme.paint_inner(painter, self.slots, self)