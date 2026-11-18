"""Compact capture circle plus an independent radial overlay; bar stays intact."""
from math import hypot
import time

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from src.ui.resources import icon, theme_color
from src.ui.toolbar.radial_menu_widget import RadialMenuWidget
from src.ui.toolbar.toolbar_widget import ToolbarWidget


class CircleDragSurface(QWidget):
    """A click captures; movement of 5 logical pixels starts toolbar dragging."""
    drag_started = Signal()
    drag_moved = Signal()
    drag_finished = Signal()
    drag_cancelled = Signal()

    def __init__(self, toolbar):
        super().__init__(toolbar)
        self.toolbar = toolbar
        self.log = None
        self._press = None
        self._moving = False
        self.setGeometry(0, 0, 60, 60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName('어플리케이션 캡처 · 드래그하여 이동 · 우클릭 도구')

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.globalPosition()
            self._moving = False
        elif event.button() == Qt.MouseButton.RightButton:
            self.toolbar.menu.open_ring(self.mapToGlobal(QPoint(30, 30)), right_tracking=True,
                                        press_position=event.globalPosition())
        event.accept()

    def mouseMoveEvent(self, event):
        if self._press is not None:
            if not event.buttons() & Qt.MouseButton.LeftButton:
                self.cancel_drag()
                return
            delta = event.globalPosition() - self._press
            if not self._moving and hypot(delta.x(), delta.y()) >= 5:
                self._moving = True
                self.drag_started.emit()
            if self._moving:
                self.drag_moved.emit()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._press is not None:
            moving = self._moving
            self._press = None
            self._moving = False
            if moving:
                self.drag_finished.emit()
            elif hypot(event.position().x() - 30, event.position().y() - 30) <= 30:
                self.toolbar.capture_or_select()
        event.accept()

    def cancel_drag(self):
        moving = self._moving
        self._press = None
        self._moving = False
        if self.mouseGrabber() is self:
            self.releaseMouse()
        if moving:
            self.drag_cancelled.emit()

    def event(self, event):
        if event.type() in (QEvent.Type.UngrabMouse, QEvent.Type.Hide):
            self.cancel_drag()
        return super().event(event)


class CircleToolbarWidget(ToolbarWidget):
    """Same signal/button contract as ToolbarWidget, rendered as a circle.

    Inherited hidden buttons are action/state objects. Both renderers therefore
    use the same controller and services without creating another toolbar.
    """
    pick_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = self.layout()
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
        layout.setContentsMargins(0, 0, 0, 0)
        self.handle.deleteLater()
        self.handle = CircleDragSurface(self)
        self.handle.drag_started.connect(self.drag_started.emit)
        self.handle.drag_moved.connect(self.drag_moved.emit)
        self.handle.drag_finished.connect(self.drag_finished.emit)
        self.handle.drag_cancelled.connect(self.drag_cancelled.emit)
        self.more_menu = self.menu
        self.more_menu.setParent(self)
        self.menu = RadialMenuWidget(self)
        self._more_pending = False
        QApplication.instance().focusWindowChanged.connect(self._focus_window_changed)
        self.setObjectName('circleToolbar')
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setFixedSize(60, 60)
        self.dock = None
        self._title = None
        self._had_target = False
        self._busy = False
        self._flash_until = 0
        self._angle = 0
        self._pulse = QTimer(self)
        self._pulse.setInterval(16)
        self._pulse.timeout.connect(self._animate)
        self.lock_button.toggled.connect(lambda _checked: self.update())
        self.set_target(None)

    def sizeHint(self):
        return QSize(60, 60)

    def show_menu(self):
        self.menu.open_ring(self.mapToGlobal(self.rect().center()))

    def show_more_menu(self):
        self.menu.close_menu()
        self._more_pending = True
        # Windows can deliver the radial popup's focus loss after it is hidden.
        QTimer.singleShot(0, self._open_more_menu)

    def _focus_window_changed(self, window):
        if self._more_pending and window is not self.menu.windowHandle():
            QTimer.singleShot(0, self._open_more_menu)

    def _open_more_menu(self):
        if not self._more_pending:
            return
        if not self.isVisible() or self.menu.isVisible():
            self._more_pending = False
            return
        ring_window = self.menu.windowHandle()
        if (QApplication.platformName() == 'windows' and ring_window is not None
                and QApplication.focusWindow() is ring_window):
            return
        self._more_pending = False
        self.more_menu.popup(self.mapToGlobal(self.rect().center()))

    def set_dock(self, edge):
        if edge == self.dock:
            return
        self.dock = edge
        self.update()
        if self.window() is not self:
            self.window()._apply_shape()
        self.menu.update()

    def capture_or_select(self):
        if self._busy:
            return
        if self._title is None:
            self.pick_requested.emit()
        else:
            self.capture_button.click()

    def activate_tool(self, tool_id):
        if tool_id == 'app_select':
            self.window_select_button.click()
        elif tool_id == 'lock':
            self.lock_button.click()
        elif tool_id == 'more':
            self.show_more_menu()
        elif tool_id == 'settings':
            self.settings_requested.emit()
        elif tool_id == 'window_size':
            self.position_requested.emit()

    def tool_enabled(self, tool_id):
        if tool_id in ('lock', 'window_size'):
            return self.lock_button.isEnabled()
        return True

    def tool_checked(self, tool_id):
        return self.lock_button.isChecked() if tool_id == 'lock' else False

    def set_target(self, target, *, lost=False):
        self._title = target.title if target is not None else None
        self._had_target |= target is not None or lost
        self.lock_button.setEnabled(target is not None)
        text = (f'{self._title} · 클릭: 캡처' if self._title is not None
                else '대상 창이 종료되었습니다 · 클릭하여 다시 지정' if self._had_target
                else '클릭하여 캡처할 어플리케이션 지정')
        self.handle.setToolTip(text + '\n드래그: 이동 · 우클릭: 도구')
        self.update()

    def set_locked(self, enabled):
        super().set_locked(enabled)
        self.update()

    def set_capture_busy(self, busy):
        self._busy = busy
        self.capture_button.setEnabled(not busy)
        if not busy:
            self._flash_until = time.monotonic() + .16
        self._pulse.start()
        self.update()

    def _animate(self):
        self._angle = (self._angle + 12) % 360
        self.update()
        if self.menu.isVisible():
            self.menu.update()
        if not self._busy and time.monotonic() >= self._flash_until:
            self._pulse.stop()

    def paint_center(self, painter, center):
        rect = QRectF(center.x() - 30, center.y() - 30, 60, 60)
        locked = self.lock_button.isChecked()
        fill = 'bg-tool-checked' if locked else 'bg-button-hover' if self.handle.underMouse() else 'bg-button'
        painter.setBrush(theme_color(fill))
        painter.setPen(QPen(theme_color('border-primary' if locked else 'border-button'), 1))
        painter.drawEllipse(rect)
        painter.setOpacity(.4 if self._title is None and self._had_target else 1)
        icon('radial_camera').paint(painter, int(center.x() - 13), int(center.y() - 13), 26, 26)
        painter.setOpacity(1)
        if locked:
            self._badge(painter, center + QPointF(18, 18), 'lock')
        if self._title is None:
            self._badge(painter, center + QPointF(-18, 18), text='!' if self._had_target else '?')
        if self._busy:
            painter.setPen(QPen(theme_color('color-capture-progress'), 3))
            painter.drawArc(rect.adjusted(3, 3, -3, -3), self._angle * 16, 110 * 16)
        if time.monotonic() < self._flash_until:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme_color('bg-capture-flash'))
            painter.drawEllipse(rect)

    @staticmethod
    def _badge(painter, center, icon_name=None, text=None):
        painter.setPen(QPen(theme_color('border-toolbar-badge'), 1))
        painter.setBrush(theme_color('bg-toolbar-badge'))
        painter.drawEllipse(center, 8, 8)
        if icon_name:
            icon(icon_name).paint(painter, int(center.x() - 5), int(center.y() - 5), 10, 10)
        else:
            painter.setPen(theme_color('color-toolbar-badge'))
            painter.drawText(QRectF(center.x() - 8, center.y() - 8, 16, 16), Qt.AlignmentFlag.AlignCenter, text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.dock:
            from PySide6.QtCore import QRect
            clips = {'right': QRect(30, 0, 30, 60), 'left': QRect(0, 0, 30, 60),
                     'top': QRect(0, 0, 60, 30), 'bottom': QRect(0, 30, 60, 30)}
            painter.setClipRect(clips[self.dock])
        self.paint_center(painter, QPointF(30, 30))

    def hideEvent(self, event):
        self._more_pending = False
        self.menu.hide()
        self.more_menu.hide()
        self.handle.cancel_drag()
        super().hideEvent(event)

    def dispose(self):
        self._more_pending = False
        self._pulse.stop()
        self.more_menu.hide()
        self.menu.close_menu()
        self.menu.deleteLater()
