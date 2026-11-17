"""Toolbar intent, separate from native window observations and Window Lock."""
from dataclasses import dataclass, field
from enum import Enum

from src.models.window_schema import WindowRef


class ToolbarMode(str, Enum):
    FREE = "free"
    ATTACHED = "attached"


class ToolbarEdge(str, Enum):
    TOP = "top"
    RIGHT = "right"
    BOTTOM = "bottom"
    LEFT = "left"


@dataclass(frozen=True)
class AttachedPlacement:
    """Edge and tangential offset in DIP.

    Offset is measured from the edge's start: left for horizontal edges, top
    for vertical edges. Normal placement is outside; maximized placement is
    inside the target. Clamping must not overwrite this intent.
    """

    edge: ToolbarEdge = ToolbarEdge.TOP
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
class ToolbarState:
    """One toolbar's connection and placement intent.

    A free toolbar may still have a target. None free_position means that
    startup placement has not been resolved yet. None maximized_placement
    requests the default inside-top-right placement avoiding caption buttons.
    Actual position, visibility, drag previews and lock data live elsewhere.
    """

    mode: ToolbarMode = ToolbarMode.FREE
    target: WindowRef | None = None
    normal_placement: AttachedPlacement = field(default_factory=AttachedPlacement)
    maximized_placement: AttachedPlacement | None = None
    free_position: ScreenPosition | None = None

    def __post_init__(self) -> None:
        if self.mode == ToolbarMode.ATTACHED and self.target is None:
            raise ValueError("An attached toolbar requires a target window.")

    @property
    def connected(self) -> bool:
        return self.target is not None

    @property
    def attached(self) -> bool:
        return self.mode == ToolbarMode.ATTACHED
