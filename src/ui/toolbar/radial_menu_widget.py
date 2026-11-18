"""A continuous right-button marking menu with radial child sectors."""
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
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.NoDropShadowWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.toolbar = toolbar
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setFixedSize(180, 212)
        self._inset = 0
        self.submenu_parent = None
        self.child_selected = None
        self.tools = TOOLBAR_TOOLS
        self.selected = None
        self._right_tracking = False
        self._opened_at = 0.0
        self._origin = QPoint()
        self._animation = QTimer(self)
        self._animation.setInterval(16)
        self._animation.timeout.connect(self.update)

    @property
    def center(self):
        return QPointF(90 + self._inset, 90 + self._inset)

    def open_ring(self, global_center, *, right_tracking=False, press_position=None):
        if self.isVisible():
            self.close_menu()
            return
        self._inset = 0
        self.submenu_parent = self.child_selected = None
        self.setFixedSize(180, 212)
        self.toolbar.more_menu.hide()
        self.selected = None
        self._right_tracking = right_tracking
        self._opened_at = time.monotonic()
        anchor = global_center.toPoint() if isinstance(global_center, QPointF) else global_center
        self._origin = press_position.toPoint() if press_position is not None else anchor
        # Keep the ring centered on the capture button, including near screen edges.
        self.move(anchor - QPoint(90, 90))
        self.show()
        self.setFocus(Qt.FocusReason.PopupFocusReason)
        self.grabMouse()
        self.grabKeyboard()
        self._animation.start()
        self.update()

    @property
    def submenu_tools(self):
        return self.tools[self.submenu_parent].children if self.submenu_parent is not None else ()

    def _open_submenu(self, index):
        if self.submenu_parent == index:
            return
        anchor = self.mapToGlobal(self.center.toPoint())
        if not self._inset:
            self._inset = 80
            self.setFixedSize(340, 372)
            self.move(anchor - QPoint(170, 170))
        self.submenu_parent = self.selected = index
        self.child_selected = None
        if self.mouseGrabber() is not self:
            self.grabMouse()
        self.update()

    def child_angles(self):
        if not self.submenu_tools:
            return []
        direction = layout_angles(self.toolbar.dock)[self.submenu_parent]
        count = len(self.submenu_tools)
        return [(direction - 60 + (i + .5) * 120 / count) % 360 for i in range(count)]

    def child_at(self, point):
        if not self.submenu_tools:
            return None
        dx, dy = point.x() - self.center.x(), point.y() - self.center.y()
        if hypot(dx, dy) < 96:
            return None
        angle = atan2(dx, -dy) * 180 / 3.141592653589793 % 360
        half = 60 / len(self.submenu_tools)
        for index, direction in enumerate(self.child_angles()):
            if abs((angle - direction + 180) % 360 - 180) <= half:
                return index
        return None

    def _track(self, global_point):
        point = QPointF(self.mapFromGlobal(global_point.toPoint()))
        distance = hypot(point.x() - self.center.x(), point.y() - self.center.y())
        if distance < 34:
            self.selected = self.submenu_parent = self.child_selected = None
        elif distance <= 92 or self.submenu_parent is None:
            index = self.index_at(point, outside=True)
            self.selected = index
            if index is not None and self.tools[index].children:
                self._open_submenu(index)
            else:
                self.submenu_parent = self.child_selected = None
        point = QPointF(self.mapFromGlobal(global_point.toPoint()))
        self.child_selected = self.child_at(point)
        self.update()

    def _execute(self, tool):
        if not self.toolbar.tool_enabled(tool.id):
            self.close_menu()
            return
        if self.toolbar.log is not None:
            self.toolbar.log.debug('TOOLBAR', f'Radial action selected id={tool.id}')
        self.close_menu()
        self.toolbar.activate_tool(tool.id)

    def close_menu(self):
        self._right_tracking = False
        self.hide()

    def hideEvent(self, event):
        self._animation.stop()
        self._right_tracking = False
        self.submenu_parent = self.child_selected = None
        self.selected = None
        if self.mouseGrabber() is self:
            self.releaseMouse()
        if self.keyboardGrabber() is self:
            self.releaseKeyboard()
        self.toolbar.update()
        super().hideEvent(event)

    def index_at(self, point, *, outside=False):
        return slot_at(point, self.center, outer=float('inf') if outside else 90,
                       dock=self.toolbar.dock, previous=self.selected)

    def choose(self, index):
        if index is None or not 0 <= index < len(self.tools):
            self.close_menu()
        elif self.tools[index].children:
            self._open_submenu(index)
        else:
            self._execute(self.tools[index])

    def mouseMoveEvent(self, event):
        if self._right_tracking:
            self._track(event.globalPosition())
        event.accept()

    def mousePressEvent(self, event):
        # The marking menu has no second click-selection phase.
        self.close_menu()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton and self._right_tracking:
            self._track(event.globalPosition())
            tool = (self.submenu_tools[self.child_selected]
                    if self.submenu_tools and self.child_selected is not None
                    else self.tools[self.selected]
                    if self.selected is not None and (not self.tools[self.selected].children
                         or self.tools[self.selected].kind == 'action'
                         or self.tools[self.selected].kind == 'toggle')
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
        outer = QRectF(center.x() - 89, center.y() - 89, 178, 178)
        inner = QRectF(center.x() - 38, center.y() - 38, 76, 76)
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
            painter.setOpacity(progress * (1 if tool.children or self.toolbar.tool_enabled(tool.id) else .35))
            painter.drawPath(path)
            angle = radians(direction)
            point = QPointF(center.x() + 64 * sin(angle), center.y() - 64 * cos(angle))
            icon('radial_' + tool.id).paint(painter, int(point.x() - 11), int(point.y() - 11), 22, 22)
        painter.restore()
        painter.save()
        if dock:
            clips = {'right': QRectF(center.x(), center.y() - 90, 90, 180),
                     'left': QRectF(center.x() - 90, center.y() - 90, 90, 180),
                     'top': QRectF(center.x() - 90, center.y() - 90, 180, 90),
                     'bottom': QRectF(center.x() - 90, center.y(), 180, 90)}
            painter.setClipRect(clips[dock])
        self.toolbar.paint_center(painter, center)
        painter.restore()
        for index, tool in enumerate(self.submenu_tools):
            direction = self.child_angles()[index]
            step = 120 / len(self.submenu_tools)
            start, sweep = 90 - direction + step / 2 - 1, -(step - 2)
            outer, inner = QRectF(center.x()-153, center.y()-153, 306, 306), QRectF(center.x()-96, center.y()-96, 192, 192)
            path = QPainterPath()
            path.arcMoveTo(outer, start)
            path.arcTo(outer, start, sweep)
            angle = radians(start + sweep)
            path.lineTo(center.x()+96*cos(angle), center.y()-96*sin(angle))
            path.arcTo(inner, start+sweep, -sweep)
            path.closeSubpath()
            hovered = index == self.child_selected
            checked = self.toolbar.tool_checked(tool.id)
            painter.setOpacity(1 if self.toolbar.tool_enabled(tool.id) else .35)
            painter.setBrush(theme_color('bg-tool-hover' if hovered else 'bg-tool-checked' if checked else 'bg-surface'))
            painter.setPen(QPen(theme_color('border-focus' if hovered else 'border-surface'), 1))
            painter.drawPath(path)
            angle = radians(direction)
            point = center + QPointF(125*sin(angle), -125*cos(angle))
            icon_name = 'unlock' if tool.id == 'lock' and not checked else tool.icon
            icon(icon_name).paint(painter, round(point.x()-9), round(point.y()-20), 18, 18)
            painter.setPen(theme_color('color-text'))
            painter.drawText(QRectF(point.x()-36, point.y()+1, 72, 20), Qt.AlignmentFlag.AlignCenter, tool.label)
        painter.setOpacity(1)
        label = (self.submenu_tools[self.child_selected].label if self.child_selected is not None
                 else self.tools[self.selected].label if self.selected is not None else '')
        painter.setPen(theme_color('color-text-muted'))
        painter.drawText(QRectF(center.x()-90, center.y()+(158 if self._inset else 96), 180, 22),
                         Qt.AlignmentFlag.AlignCenter, label)
