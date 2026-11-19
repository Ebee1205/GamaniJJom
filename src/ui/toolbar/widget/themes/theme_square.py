"""Square theme: rounded-square cover; the radial fan unrolls into straight strips.

Layout is built once in a local frame (cover centre at the origin, strip running
along +x, children stacked along +y/-y) and rotated onto the chosen direction.
"""
from math import ceil, floor

from PySide6.QtCore import QPointF, QRectF, QSize
from PySide6.QtGui import QPainterPath, QTransform

from src.ui.toolbar.widget.toolbar_theme import (
    ZONE_CHILD, ZONE_DEAD, ZONE_PRIMARY, SlotLayout, ToolbarTheme, register_theme,
)

COVER = 60
CORNER = 14
X0 = 38                       # cover centre -> first slot (same gap the ring leaves)
SLOT_LEN, SLOT_THICK = 48, 48
CHILD_W, CHILD_H, CHILD_GAP = 72, 48, 4
LABEL_W, LABEL_H = 170, 22
STICKY = 4                    # hysteresis, like the ring's 2.5 degrees

_OUTWARD = {'right': 'right', 'left': 'left', 'top': 'up', 'bottom': 'down'}
_ANGLE = {'right': 0, 'down': 90, 'left': 180, 'up': 270}


def _cell_dims(direction):
    """(along the strip, step across it) of a child cell in the local frame.
    Cells stay upright on screen, so the roles of width and height swap when the strip is vertical."""
    return (CHILD_W, CHILD_H) if direction in ('right', 'left') else (CHILD_H, CHILD_W)


class StripLayout(SlotLayout):
    def __init__(self, tools, dock, anchor, bounds):
        super().__init__(tools, dock)
        self.direction, self.side = self._choose(anchor, bounds)
        extent = self._extent(self.direction, self.side)
        left, top = floor(extent.left() + 1e-6), floor(extent.top() + 1e-6)
        right, bottom = ceil(extent.right() - 1e-6), ceil(extent.bottom() - 1e-6)
        self._size = QSize(right - left, bottom - top)
        self._center = QPointF(-left, -top)
        self._map = QTransform()
        self._map.translate(-left, -top)
        self._map.rotate(_ANGLE[self.direction])
        self._unmap, _ = self._map.inverted()
        c = self._map.map(self._label_center(self.direction, self.side))
        self._label = QRectF(c.x() - LABEL_W / 2, c.y() - LABEL_H / 2, LABEL_W, LABEL_H)

    # ---- Direction / side selection ---------------------------------------------------
    def _choose(self, anchor, bounds):
        directions = [_OUTWARD[self.dock]] if self.dock else ['right', 'left', 'down', 'up']
        options = [(d, s) for d in directions for s in (1, -1)]
        if bounds is not None:
            area = QRectF(bounds)
            for direction, side in options:
                if area.contains(self._extent(direction, side).translated(QPointF(anchor))):
                    return direction, side
        return options[0]

    def _label_center(self, direction, side):
        n = len(self.tools)
        if direction in ('right', 'left'):   # beside the strip, opposite the children
            return QPointF(X0 + n * SLOT_LEN / 2, -side * (SLOT_THICK / 2 + CHILD_GAP + LABEL_H / 2))
        return QPointF(-(COVER / 2 + CHILD_GAP + LABEL_H / 2), 0)   # behind the cover

    def _column_rect(self, slot, count, side, direction):
        along, step = _cell_dims(direction)
        x = X0 + (slot + .5) * SLOT_LEN - along / 2
        y = (SLOT_THICK / 2 + CHILD_GAP) if side > 0 else -(SLOT_THICK / 2 + CHILD_GAP + count * step)
        return QRectF(x, y, along, count * step)

    def _extent(self, direction, side):
        """Bounding box (cover centre = origin) of everything this layout can draw."""
        rotation = QTransform().rotate(_ANGLE[direction])
        rects = [QRectF(-COVER / 2, -COVER / 2, COVER, COVER),
                 QRectF(X0, -SLOT_THICK / 2, len(self.tools) * SLOT_LEN, SLOT_THICK)]
        rects += [self._column_rect(i, len(t.children), side, direction) for i, t in enumerate(self.tools) if t.children]
        boxes = [rotation.mapRect(r) for r in rects]
        c = rotation.map(self._label_center(direction, side))
        boxes.append(QRectF(c.x() - LABEL_W / 2, c.y() - LABEL_H / 2, LABEL_W, LABEL_H))
        union = boxes[0]
        for box in boxes[1:]:
            union = union.united(box)
        return union

    # ---- SlotLayout -----------------------------------------------------------------
    @property
    def size(self):
        return self._size

    @property
    def center(self):
        return self._center

    def _local(self, point):
        return self._unmap.map(QPointF(point))

    def zone(self, point):
        q = self._local(point)
        if q.x() < X0:
            return ZONE_DEAD
        return ZONE_CHILD if self.side * q.y() > SLOT_THICK / 2 + CHILD_GAP else ZONE_PRIMARY

    def slot_at(self, point, previous=None):
        x = self._local(point).x()
        if previous is not None and X0 + previous * SLOT_LEN - STICKY <= x <= X0 + (previous + 1) * SLOT_LEN + STICKY:
            return previous
        return min(len(self.tools) - 1, max(0, int((x - X0) // SLOT_LEN)))

    def child_at(self, point):
        count = len(self.child_tools)
        if not count:
            return None
        q = self._local(point)
        along, step = _cell_dims(self.direction)
        if abs(q.x() - (X0 + (self.submenu_parent + .5) * SLOT_LEN)) > along / 2:
            return None
        depth = self.side * q.y() - (SLOT_THICK / 2 + CHILD_GAP)
        if depth < 0:
            return None
        return min(count - 1, int(depth // step))

    def slot_path(self, index):
        rect = QRectF(X0 + index * SLOT_LEN, -SLOT_THICK / 2, SLOT_LEN, SLOT_THICK).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 6, 6)
        return self._map.map(path)

    def slot_anchor(self, index):
        return self._map.map(QPointF(X0 + (index + .5) * SLOT_LEN, 0))

    def _child_rect(self, index):
        along, step = _cell_dims(self.direction)
        column = self._column_rect(self.submenu_parent, len(self.child_tools), self.side, self.direction)
        k = index if self.side > 0 else len(self.child_tools) - 1 - index   # index 0 is nearest the strip
        return QRectF(column.x(), column.y() + k * step, along, step)

    def child_path(self, index):
        path = QPainterPath()
        path.addRoundedRect(self._child_rect(index).adjusted(1, 1, -1, -1), 6, 6)
        return self._map.map(path)

    def child_anchor(self, index):
        return self._map.map(self._child_rect(index).center())

    def label_rect(self):
        return self._label


class ThemeSquare(ToolbarTheme):
    name = 'square'
    cover_extent = COVER

    def cover_path(self, rect):
        path = QPainterPath()
        path.addRoundedRect(rect, CORNER, CORNER)
        return path

    def create_layout(self, tools, dock, anchor, bounds):
        return StripLayout(tools, dock, anchor, bounds)


register_theme(ThemeSquare.name, ThemeSquare)