"""Pure native-pixel geometry with monitor-relative DIP preferences."""
from math import hypot

from src.models.toolbar_enum import ToolbarEdge
from src.models.toolbar_event_schema import SnapCandidate
from src.models.toolbar_schema import AttachedPlacement, ScreenPosition
from src.models.window_schema import WindowRect
from src.services.toolbar_state_service import SNAP_DISTANCE_DIP


def to_screen_position(rect, monitor):
    return ScreenPosition(monitor.device, (rect.x - monitor.work_area.x) / monitor.scale,
                          (rect.y - monitor.work_area.y) / monitor.scale)


def from_screen_position(position, monitor):
    return (monitor.work_area.x + round(position.x_dip * monitor.scale),
            monitor.work_area.y + round(position.y_dip * monitor.scale))


def clamp_position(x, y, size, area):
    return (max(area.x, min(x, area.x + max(0, area.width - size.width))),
            max(area.y, min(y, area.y + max(0, area.height - size.height))))


def attached_position(target, toolbar, placement, scale, *, maximized=False):
    # None means the default maximized placement, below caption buttons.
    placement = placement or AttachedPlacement(ToolbarEdge.RIGHT, 48)
    offset = round(placement.offset_dip * scale)
    edge = placement.edge
    if edge == ToolbarEdge.TOP:
        x, y = target.x + offset, target.y if maximized else target.y - toolbar.height
    elif edge == ToolbarEdge.BOTTOM:
        x, y = target.x + offset, target.y + target.height - (toolbar.height if maximized else 0)
    elif edge == ToolbarEdge.LEFT:
        x, y = target.x if maximized else target.x - toolbar.width, target.y + offset
    else:
        x, y = target.x + target.width - (toolbar.width if maximized else 0), target.y + offset
    if maximized:
        x, y = clamp_position(x, y, toolbar, target)
        # Reserve a conservative title-button region, including custom frames.
        if y < target.y + round(40 * scale) and x + toolbar.width > target.x + target.width - round(150 * scale):
            y = target.y + round(48 * scale)
    return x, y


def _gap(a0, a1, b0, b1):
    return max(a0 - b1, b0 - a1, 0)


def snap_candidate(target, toolbar, scale, *, maximized=False):
    """Distance from toolbar rectangle to finite target edge segments."""
    r = target.rect
    right, bottom = r.x + r.width, r.y + r.height
    edges = (
        (ToolbarEdge.TOP, r.x, right, r.y, r.y),
        (ToolbarEdge.RIGHT, right, right, r.y, bottom),
        (ToolbarEdge.BOTTOM, r.x, right, bottom, bottom),
        (ToolbarEdge.LEFT, r.x, r.x, r.y, bottom),
    )
    best = None
    for edge, x0, x1, y0, y1 in edges:
        distance = hypot(_gap(toolbar.x, toolbar.x + toolbar.width, x0, x1),
                         _gap(toolbar.y, toolbar.y + toolbar.height, y0, y1)) / scale
        if distance > SNAP_DISTANCE_DIP or (best and distance >= best.distance_dip):
            continue
        offset = ((toolbar.x - r.x) if edge in (ToolbarEdge.TOP, ToolbarEdge.BOTTOM)
                  else (toolbar.y - r.y)) / scale
        best = SnapCandidate(target.reference, AttachedPlacement(edge, offset), distance, maximized)
    return best
