"""Toolbar theme contract.

A theme owns *shape only*: the cover outline, the slot geometry with its hit
testing, and the default painting built on them. Behaviour (click, drag,
expand/collapse, tool dispatch) lives in the cover/inner widgets, so switching
a theme never changes what the toolbar does. Colours come from the theme.qss
tokens through theme_color().

Add a theme: subclass ToolbarTheme, return your SlotLayout from create_layout(),
then register_theme('name', YourTheme). Select it with ToolbarWidget.set_theme()
or from QSS:  QWidget#toolbarWindow { qproperty-toolbarTheme: "name"; }
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPen, QRegion

from src.ui.resources import icon, theme_color

ZONE_DEAD, ZONE_PRIMARY, ZONE_CHILD = 'dead', 'primary', 'child'

# Names that used to exist as renderer modes. 'bar' was the old rectangular toolbar.
THEME_ALIASES = {'bar': 'square'}


@dataclass(frozen=True)
class CoverState:
    """Everything a theme needs to paint the cover; built by the cover widget."""
    dock: str | None = None
    locked: bool = False
    hovered: bool = False
    has_target: bool = False
    had_target: bool = False
    primary_screen: bool = False
    busy: bool = False
    spin_angle: int = 0
    flashing: bool = False


class SlotLayout(ABC):
    """Geometry of one expanded menu: where slots/children are and what a point hits.

    Coordinates are in the inner window. `zone()` classifies a pointer position:
    ZONE_DEAD (over the cover: nothing selected), ZONE_PRIMARY (top-level slots)
    or ZONE_CHILD (the child area of the open submenu).
    """

    def __init__(self, tools, dock):
        self.tools = tools
        self.dock = dock
        self.submenu_parent = None

    @property
    @abstractmethod
    def size(self) -> QSize: ...

    @property
    @abstractmethod
    def center(self) -> QPointF:
        """Where the cover centre sits inside the inner window."""

    def window_origin(self, anchor: QPoint) -> QPoint:
        """Global top-left that puts the cover centre on `anchor`."""
        return anchor - self.center.toPoint()

    @property
    def child_tools(self):
        return self.tools[self.submenu_parent].children if self.submenu_parent is not None else ()

    def open_submenu(self, index) -> bool:
        """Open children of slot `index`. Return True if size/centre changed."""
        self.submenu_parent = index
        return False

    def close_submenu(self):
        self.submenu_parent = None

    @abstractmethod
    def zone(self, point: QPointF) -> str: ...

    @abstractmethod
    def slot_at(self, point: QPointF, previous=None): ...

    @abstractmethod
    def child_at(self, point: QPointF): ...

    @abstractmethod
    def slot_path(self, index) -> QPainterPath: ...

    @abstractmethod
    def slot_anchor(self, index) -> QPointF:
        """Centre for the slot icon."""

    @abstractmethod
    def child_path(self, index) -> QPainterPath: ...

    @abstractmethod
    def child_anchor(self, index) -> QPointF:
        """Centre for the child icon + label pair."""

    @abstractmethod
    def label_rect(self) -> QRectF:
        """Where the hovered tool's name is drawn."""


class ToolbarTheme(ABC):
    name = ''
    cover_extent = 60  # side of the square that bounds the cover

    @property
    def cover_size(self) -> QSize:
        return QSize(self.cover_extent, self.cover_extent)

    # ---- Shape: the parts a theme must provide --------------------------------------
    @abstractmethod
    def cover_path(self, rect: QRectF) -> QPainterPath:
        """Outline of the cover inside `rect`."""

    @abstractmethod
    def create_layout(self, tools, dock, anchor: QPoint, bounds: QRect | None) -> SlotLayout:
        """Layout for one expansion. `anchor` is the global cover centre and
        `bounds` the available screen area (themes may use it to choose a side)."""

    # ---- Shape: overridable defaults ------------------------------------------------
    def cover_contains(self, point) -> bool:
        s = self.cover_extent
        return self.cover_path(QRectF(0, 0, s, s)).contains(QPointF(point))

    @staticmethod
    def visible_rect(rect: QRectF, dock) -> QRectF:
        """The half of `rect` that stays visible when docked to an edge."""
        if dock is None:
            return rect
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        return {'right': QRectF(x + w / 2, y, w / 2, h), 'left': QRectF(x, y, w / 2, h),
                'top': QRectF(x, y, w, h / 2), 'bottom': QRectF(x, y + h / 2, w, h / 2)}[dock]

    def clip_to_dock(self, region: QRegion, dock) -> QRegion:
        if dock is None:
            return region
        s = self.cover_extent
        return region.intersected(QRegion(self.visible_rect(QRectF(0, 0, s, s), dock).toRect()))

    def cover_mask(self, dock) -> QRegion | None:
        """Window mask (click-through outside the shape); None clears the mask."""
        s = self.cover_extent
        region = QRegion(self.cover_path(QRectF(0, 0, s, s)).toFillPolygon().toPolygon())
        return self.clip_to_dock(region, dock)

    # ---- Painting: default implementation built on the shape ------------------------
    def paint_cover(self, painter: QPainter, center: QPointF, state: CoverState):
        s = self.cover_extent
        rect = QRectF(center.x() - s / 2, center.y() - s / 2, s, s)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if state.dock:
            painter.setClipRect(self.visible_rect(rect, state.dock))
        fill = 'bg-tool-checked' if state.locked else 'bg-button-hover' if state.hovered else 'bg-button'
        painter.setBrush(theme_color(fill))
        painter.setPen(QPen(theme_color('border-primary' if state.locked else 'border-button'), 1))
        painter.drawPath(self.cover_path(rect))
        painter.setOpacity(.4 if not state.has_target and state.had_target else 1)
        icon('radial_monitor' if state.primary_screen else 'radial_camera').paint(
            painter, int(center.x() - 13), int(center.y() - 13), 26, 26)
        painter.setOpacity(1)
        if state.locked:
            self.paint_badge(painter, center + QPointF(18, 18), 'lock')
        if not state.has_target and not state.primary_screen:
            self.paint_badge(painter, center + QPointF(-18, 18), text='!' if state.had_target else '?')
        if state.busy:
            self.paint_busy(painter, rect, state.spin_angle)
        if state.flashing:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme_color('bg-capture-flash'))
            painter.drawPath(self.cover_path(rect))
        painter.restore()

    def paint_busy(self, painter: QPainter, rect: QRectF, angle: int):
        """Spinner: a short arc that travels along the cover outline."""
        path = self.cover_path(rect.adjusted(3, 3, -3, -3))
        start = (angle % 360) / 360
        points = [path.pointAtPercent((start + 110 / 360 * i / 24) % 1.0) for i in range(25)]
        painter.setPen(QPen(theme_color('color-capture-progress'), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolyline(points)

    @staticmethod
    def paint_badge(painter, center, icon_name=None, text=None):
        painter.setPen(QPen(theme_color('border-toolbar-badge'), 1))
        painter.setBrush(theme_color('bg-toolbar-badge'))
        painter.drawEllipse(center, 8, 8)
        if icon_name:
            icon(icon_name).paint(painter, int(center.x() - 5), int(center.y() - 5), 10, 10)
        else:
            painter.setPen(theme_color('color-toolbar-badge'))
            painter.drawText(QRectF(center.x() - 8, center.y() - 8, 16, 16), Qt.AlignmentFlag.AlignCenter, text)

    def paint_inner(self, painter: QPainter, layout: SlotLayout, view):
        """Paint an expanded menu. `view` is the inner widget (tools, selected,
        child_selected, progress, toolbar)."""
        toolbar, center, progress = view.toolbar, layout.center, view.progress
        painter.save()
        painter.translate(center)
        scale = .45 + .55 * progress
        painter.scale(scale, scale)
        painter.translate(-center)
        for index, tool in enumerate(view.tools):
            active = toolbar.tool_checked(tool.id)
            hovered = index == view.selected
            fill = (('bg-primary-hover' if hovered else 'bg-tool-checked') if active
                    else 'bg-tool-hover' if hovered else 'bg-surface')
            painter.setBrush(theme_color(fill))
            painter.setPen(QPen(theme_color('border-surface'), 1))
            painter.setOpacity(progress * (1 if tool.children or toolbar.tool_enabled(tool.id) else .35))
            painter.drawPath(layout.slot_path(index))
            anchor = layout.slot_anchor(index)
            icon('radial_' + tool.id).paint(painter, int(anchor.x() - 11), int(anchor.y() - 11), 22, 22)
        painter.restore()

        self.paint_cover(painter, center, toolbar.cover_state())

        for index, tool in enumerate(layout.child_tools):
            hovered = index == view.child_selected
            checked = toolbar.tool_checked(tool.id)
            painter.setOpacity(1 if toolbar.tool_enabled(tool.id) else .35)
            painter.setBrush(theme_color('bg-tool-hover' if hovered else 'bg-tool-checked' if checked else 'bg-surface'))
            painter.setPen(QPen(theme_color('border-focus' if hovered else 'border-surface'), 1))
            painter.drawPath(layout.child_path(index))
            anchor = layout.child_anchor(index)
            icon_name = 'unlock' if tool.id == 'lock' and not checked else tool.icon
            icon(icon_name).paint(painter, round(anchor.x() - 9), round(anchor.y() - 20), 18, 18)
            painter.setPen(theme_color('color-text'))
            painter.drawText(QRectF(anchor.x() - 36, anchor.y() + 1, 72, 20), Qt.AlignmentFlag.AlignCenter, tool.label)

        painter.setOpacity(1)
        label = (layout.child_tools[view.child_selected].label if view.child_selected is not None
                 else view.tools[view.selected].label if view.selected is not None else '')
        painter.setPen(theme_color('color-text-muted'))
        painter.drawText(layout.label_rect(), Qt.AlignmentFlag.AlignCenter, label)


# ---- Registry ---------------------------------------------------------------------
_THEMES: dict[str, Callable[[], ToolbarTheme]] = {}


def register_theme(name: str, factory: Callable[[], ToolbarTheme]):
    _THEMES[name] = factory


def available_themes() -> tuple[str, ...]:
    return tuple(_THEMES)


def create_theme(name: str) -> ToolbarTheme:
    factory = _THEMES.get(THEME_ALIASES.get(name, name))
    if factory is None:
        raise ValueError(f'Unknown toolbar theme {name!r}; available: {", ".join(_THEMES) or "none"}')
    return factory()