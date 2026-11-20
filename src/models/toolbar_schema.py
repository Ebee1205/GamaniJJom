"""Toolbar intent, separate from native window observations and Window Lock."""
from dataclasses import dataclass, field

from src.models.window_schema import WindowRef, WindowRect
import src.models.toolbar_enum as toolbar_enum


@dataclass(frozen=True)
class MonitorGeometry:
    device: str
    bounds: WindowRect
    work_area: WindowRect
    scale: float


@dataclass(frozen=True)
class DragSession:
    """Transient gesture; dragging always overrides normal Z-order to topmost."""

    cursor_start: tuple[int, int]
    toolbar_start: WindowRect
    scale_start: float


def toolbar_is_topmost(state: "ToolbarState", *, dragging: bool) -> bool:
    return dragging or not state.attached


@dataclass(frozen=True)
class AttachedPlacement:
    """Edge and tangential offset in DIP.

    Offset is measured from the edge's start: left for horizontal edges, top
    for vertical edges. Normal placement is outside; maximized placement is
    inside the target. Clamping must not overwrite this intent.
    """

    edge: toolbar_enum.ToolbarEdge = toolbar_enum.ToolbarEdge.TOP
    offset_dip: float = 0.0


@dataclass(frozen=True)
class ScreenPosition:
    """Toolbar top-left in DIP relative to a monitor's work-area origin.

    monitor_id is a stable display identifier supplied by the adapter, not
    a runtime HMONITOR. Missing monitors are resolved by the placement layer.
    """

    monitor_id: str
    x_dip: float
    y_dip: float


@dataclass(frozen=True)
class TargetRelativePosition:
    """Free toolbar top-left relative to its target's top-left, in target DIP."""
    x_dip: float
    y_dip: float


@dataclass(frozen=True)
class ToolbarState:
    """One toolbar's connection and placement intent.

    Free + no target, free + target and attached + target are three statuses.
    A connected free toolbar follows its target using free_anchor. None free_position means that
    startup placement has not been resolved yet. None maximized_placement
    requests the default inside-top-right placement avoiding caption buttons.
    Actual position, visibility, drag previews and lock data live elsewhere.
    """

    mode: toolbar_enum.ToolbarMode = toolbar_enum.ToolbarMode.FREE
    target: WindowRef | None = None
    normal_placement: AttachedPlacement = field(default_factory=AttachedPlacement)
    maximized_placement: AttachedPlacement | None = None
    free_position: ScreenPosition | None = None
    free_anchor: TargetRelativePosition | None = None

    def __post_init__(self) -> None:
        if self.mode == toolbar_enum.ToolbarMode.ATTACHED and self.target is None:
            raise ValueError("An attached toolbar requires a target window.")
        if self.free_anchor is not None and (self.attached or self.target is None):
            raise ValueError("A free anchor requires a connected, unattached toolbar.")

    @property
    def connected(self) -> bool:
        return self.target is not None

    @property
    def capture_mode(self) -> toolbar_enum.CaptureMode:
        return (toolbar_enum.CaptureMode.WINDOW if self.connected
                else toolbar_enum.CaptureMode.PRIMARY_SCREEN)

    @property
    def attached(self) -> bool:
        return self.mode == toolbar_enum.ToolbarMode.ATTACHED

    @property
    def status(self) -> toolbar_enum.ToolbarStatus:
        if self.attached:
            return toolbar_enum.ToolbarStatus.ATTACHED
        return (toolbar_enum.ToolbarStatus.CONNECTED_FREE if self.connected
                else toolbar_enum.ToolbarStatus.DISCONNECTED)
