"""Radial Toolbar Prototype v0.4 geometry and mouse interaction."""
from math import atan2, cos, hypot, radians, sin
import time

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from src.models.toolbar_tool_schema import TOOLBAR_TOOLS
from src.ui.resources import icon, theme_color


def layout_angles(dock=None, count=3):
    span = (180 if dock else 360) / count
    outward = {'right': 90, 'bottom': 180, 'left': 270, 'top': 0}
    direction = 1 if dock in ('right', 'top') else -1
    return [((outward[dock] + direction * (i - (count - 1) / 2) * span)
             if dock else i * span) % 360 for i in range(count)]


def slot_at(point, center, *, inner=34, outer=90, count=3, dock=None, previous=None):
    dx, dy = point.x() - center.x(), point.y() - center.y()
    if not inner <= hypot(dx, dy) <= outer:
        return None
    angle = atan2(dx, -dy) * 180 / 3.141592653589793 % 360
    centers = layout_angles(dock, count)
    def distance(i):
        return abs((angle - centers[i] + 180) % 360 - 180)
    best = min(range(count), key=distance)
    if previous is not None and distance(previous) < (90 if dock else 180) / count + 2.5:
        return previous
    return best


class RadialMenuWidget(QWidget):
    DIAMETER = 180

    def __init__(self, toolbar):
        super().__init__(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.NoDropShadowWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.toolbar = toolbar
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setFixedSize(180, 212)
        self.tools = TOOLBAR_TOOLS
        self.selected = None
        self._right_tracking = False
        self._pressed = None
        self._opened_at = 0.0
        self._origin = QPoint()
        self._animation = QTimer(self)
        self._animation.setInterval(16)
        self._animation.timeout.connect(self.update)

    @property
    def center(self):
        return QPointF(90, 90)

    def open_ring(self, global_center, *, right_tracking=False, press_position=None):
        if self.isVisible():
            self.close_menu()
            return
        self.toolbar.more_menu.hide()
        self.selected = self._pressed = None
        self._right_tracking = right_tracking
        self._opened_at = time.monotonic()
        anchor = global_center.toPoint() if isinstance(global_center, QPointF) else global_center
        self._origin = press_position.toPoint() if press_position is not None else anchor
        # Keep the ring centered on the capture button, including near screen edges.
        self.move(anchor - QPoint(90, 90))
        self.show()
        self.setFocus(Qt.FocusReason.PopupFocusReason)
        self.grabMouse()
        self._animation.start()
        self.update()

    def close_menu(self):
        self._right_tracking = False
        self.hide()

    def hideEvent(self, event):
        self._animation.stop()
        self._right_tracking = False
        self.selected = self._pressed = None
        if self.mouseGrabber() is self:
            self.releaseMouse()
        self.toolbar.update()
        super().hideEvent(event)

    def index_at(self, point, *, outside=False):
        return slot_at(point, self.center, outer=float('inf') if outside else 90,
                       dock=self.toolbar.dock, previous=self.selected)

    def choose(self, index):
        if index is None or not 0 <= index < len(self.tools):
            self.close_menu()
            return
        tool = self.tools[index]
        if not self.toolbar.tool_enabled(tool.id):
            return
        if self.toolbar.log is not None:
            self.toolbar.log.debug("TOOLBAR", f"Radial action selected id={tool.id}")
        self.close_menu()
        self.toolbar.activate_tool(tool.id)

    def mouseMoveEvent(self, event):
        self.selected = self.index_at(event.position(), outside=self._right_tracking)
        self.update()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            index = self.index_at(event.position())
            if index is None:
                self.close_menu()
            else:
                self._pressed = index
        elif event.button() == Qt.MouseButton.RightButton and not self._right_tracking:
            self.close_menu()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton and self._right_tracking:
            self._right_tracking = False
            delta = event.globalPosition() - QPointF(self._origin)
            index = self.index_at(event.position(), outside=True)
            if hypot(delta.x(), delta.y()) >= 5 and index is not None:
                self.choose(index)  # A quick directional drag still selects its tool.
            elif time.monotonic() - self._opened_at < .2:
                self.update()  # A stationary short right-click keeps the ring open.
            else:
                self.close_menu()
        elif event.button() == Qt.MouseButton.LeftButton:
            index = self.index_at(event.position())
            if self._pressed is not None and index == self._pressed:
                self.choose(index)
            self._pressed = None
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close_menu()
            event.accept()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        elapsed = min(1.0, (time.monotonic() - self._opened_at) / .13)
        progress = 1 - (1 - elapsed) ** 3
        if elapsed >= 1:
            self._animation.stop()
        center = self.center
        painter.save()
        painter.translate(center)
        painter.scale(.45 + .55 * progress, .45 + .55 * progress)
        painter.translate(-center)
        painter.setOpacity(progress)
        outer = QRectF(1, 1, 178, 178)
        inner = QRectF(52, 52, 76, 76)
        dock = self.toolbar.dock
        step = (180 if dock else 360) / len(self.tools)
        for index, tool in enumerate(self.tools):
            direction = layout_angles(dock)[index]
            # No angular gap: neighbouring slices share an edge like cake slices.
            start, sweep = 90 - direction + step / 2, -step
            path = QPainterPath()
            path.arcMoveTo(outer, start)
            path.arcTo(outer, start, sweep)
            angle = radians(start + sweep)
            path.lineTo(center.x() + 38 * cos(angle), center.y() - 38 * sin(angle))
            path.arcTo(inner, start + sweep, -sweep)
            path.closeSubpath()
            active = self.toolbar.tool_checked(tool.id)
            hovered = index == self.selected
            fill = (('bg-primary-hover' if hovered else 'bg-tool-checked') if active
                    else 'bg-tool-hover' if hovered else 'bg-surface')
            painter.setBrush(theme_color(fill))
            painter.setPen(QPen(theme_color('border-surface'), 1))
            painter.setOpacity(progress * (1 if self.toolbar.tool_enabled(tool.id) else .35))
            painter.drawPath(path)
            angle = radians(direction)
            point = QPointF(center.x() + 64 * sin(angle), center.y() - 64 * cos(angle))
            icon('radial_' + tool.id).paint(painter, int(point.x() - 11), int(point.y() - 11), 22, 22)
        painter.restore()
        painter.save()
        if dock:
            clips = {'right': QRectF(90, 0, 90, 180), 'left': QRectF(0, 0, 90, 180),
                     'top': QRectF(0, 0, 180, 90), 'bottom': QRectF(0, 90, 180, 90)}
            painter.setClipRect(clips[dock])
        self.toolbar.paint_center(painter, center)
        painter.restore()
        if self.selected is not None:
            tool = self.tools[self.selected]
            label = tool.label
            if tool.id == 'lock':
                label += ' (켜짐)' if self.toolbar.tool_checked(tool.id) else ' (꺼짐)'
            painter.setPen(theme_color('color-text-muted'))
            painter.drawText(QRectF(0, 186, 180, 22), Qt.AlignmentFlag.AlignCenter, label)