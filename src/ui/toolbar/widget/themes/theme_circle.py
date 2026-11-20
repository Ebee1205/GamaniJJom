"""Default theme: circular cover and a radial (marking) menu."""
from math import atan2, cos, hypot, pi, radians, sin

from PySide6.QtCore import QPointF, QRectF, QSize
from PySide6.QtGui import QPainterPath, QPen

from src.ui.resources import theme_color

from src.ui.toolbar.widget.toolbar_theme import (
    ZONE_CHILD, ZONE_DEAD, ZONE_PRIMARY, SlotLayout, ToolbarTheme, register_theme,
)

COVER = 60
BASE_CENTER = 90            # ring centre in the closed window
SUBMENU_INSET = 80          # the window grows by this on every side for the child ring
CLOSED_SIZE, OPEN_SIZE = QSize(180, 212), QSize(340, 372)
DEAD_RADIUS = 34            # inside: nothing selected
PRIMARY_RADIUS = 92         # beyond: child-ring area
RING_OUTER, RING_INNER = 89, 38
CHILD_OUTER, CHILD_INNER = 153, 96
SLOT_ICON_RADIUS, CHILD_ICON_RADIUS = 64, 125
CHILD_SWEEP = 360 / 8


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
    angle = atan2(dx, -dy) * 180 / pi % 360
    centers = layout_angles(dock, count)

    def distance(i):
        return abs((angle - centers[i] + 180) % 360 - 180)
    best = min(range(count), key=distance)
    if previous is not None and distance(previous) < (90 if dock else 180) / count + 2.5:
        return previous
    return best


def _sector(center, outer_radius, inner_radius, start, sweep):
    """Ring sector between two radii; angles in Qt's counter-clockwise degrees."""
    outer = QRectF(center.x() - outer_radius, center.y() - outer_radius, 2 * outer_radius, 2 * outer_radius)
    inner = QRectF(center.x() - inner_radius, center.y() - inner_radius, 2 * inner_radius, 2 * inner_radius)
    path = QPainterPath()
    path.arcMoveTo(outer, start)
    path.arcTo(outer, start, sweep)
    angle = radians(start + sweep)
    path.lineTo(center.x() + inner_radius * cos(angle), center.y() - inner_radius * sin(angle))
    path.arcTo(inner, start + sweep, -sweep)
    path.closeSubpath()
    return path


class RadialLayout(SlotLayout):
    """Top-level slots as ring sectors; children as a second, wider ring."""

    def __init__(self, tools, dock):
        super().__init__(tools, dock)
        self._inset = 0

    @property
    def count(self):
        return len(self.tools)

    @property
    def size(self):
        return OPEN_SIZE if self._inset else CLOSED_SIZE

    @property
    def center(self):
        return QPointF(BASE_CENTER + self._inset, BASE_CENTER + self._inset)

    def open_submenu(self, index):
        grew = not self._inset
        self._inset = SUBMENU_INSET
        self.submenu_parent = index
        return grew

    def _distance(self, point):
        return hypot(point.x() - self.center.x(), point.y() - self.center.y())

    def zone(self, point):
        distance = self._distance(point)
        if distance < DEAD_RADIUS:
            return ZONE_DEAD
        return ZONE_PRIMARY if distance <= PRIMARY_RADIUS else ZONE_CHILD

    def slot_at(self, point, previous=None):
        # Marking menu: direction decides, distance does not (outer=inf).
        return slot_at(point, self.center, outer=float('inf'), count=self.count,
                       dock=self.dock, previous=previous)

    def _slot_direction(self, index):
        return layout_angles(self.dock, self.count)[index]

    def slot_path(self, index):
        # No angular gap: neighbouring slices share an edge like cake slices.
        step = (180 if self.dock else 360) / self.count
        start = 90 - self._slot_direction(index) + step / 2
        return _sector(self.center, RING_OUTER, RING_INNER, start, -step)

    def slot_anchor(self, index):
        angle = radians(self._slot_direction(index))
        return QPointF(self.center.x() + SLOT_ICON_RADIUS * sin(angle),
                       self.center.y() - SLOT_ICON_RADIUS * cos(angle))

    def _child_angles(self):
        count = len(self.child_tools)
        if not count:
            return []
        direction = self._slot_direction(self.submenu_parent)
        return [(direction + (i - (count - 1) / 2) * CHILD_SWEEP) % 360 for i in range(count)]

    def child_at(self, point):
        count = len(self.child_tools)
        if not count or self._distance(point) < CHILD_INNER:
            return None
        angle = atan2(point.x() - self.center.x(), -(point.y() - self.center.y())) * 180 / pi % 360
        half = CHILD_SWEEP / 2
        for index, direction in enumerate(self._child_angles()):
            if abs((angle - direction + 180) % 360 - 180) <= half:
                return index
        return None

    def child_path(self, index):
        start = 90 - self._child_angles()[index] + CHILD_SWEEP / 2
        return _sector(self.center, CHILD_OUTER, CHILD_INNER, start, -CHILD_SWEEP)

    def child_anchor(self, index):
        angle = radians(self._child_angles()[index])
        return self.center + QPointF(CHILD_ICON_RADIUS * sin(angle), -CHILD_ICON_RADIUS * cos(angle))

    def label_rect(self):
        c = self.center
        return QRectF(c.x() - 90, c.y() + (158 if self._inset else 96), 180, 22)


class ThemeCircle(ToolbarTheme):
    name = 'circle'
    cover_extent = COVER

    def cover_path(self, rect):
        path = QPainterPath()
        path.addEllipse(rect)
        return path

    def cover_contains(self, point):
        return hypot(point.x() - COVER / 2, point.y() - COVER / 2) <= COVER / 2

    def cover_mask(self, dock):
        """Keep the translucent antialiased edge instead of a binary window mask."""
        return None

    def paint_busy(self, painter, rect, angle):
        painter.setPen(QPen(theme_color('color-capture-progress'), 3))
        painter.drawArc(rect.adjusted(3, 3, -3, -3), angle * 16, 110 * 16)

    def create_layout(self, tools, dock, anchor, bounds):
        return RadialLayout(tools, dock)


register_theme(ThemeCircle.name, ThemeCircle)
