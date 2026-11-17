"""Confirmed toolbar inputs and transition results; no Qt or Win32 dependencies.

Window selection and snap candidates must be validated by the caller before
dispatch. Position is the actual last displayed/drop position, converted into
monitor-relative DIP. Never pass minimized window coordinates as that position.
"""
from dataclasses import dataclass
from math import isfinite

from src.models.toolbar_schema import AttachedPlacement, ScreenPosition, ToolbarState
from src.models.window_schema import WindowRef, WindowState


@dataclass(frozen=True)
class TargetSelected:
    target: WindowRef


@dataclass(frozen=True)
class SnapCandidate:
    target: WindowRef
    placement: AttachedPlacement
    distance_dip: float
    maximized: bool = False

    def __post_init__(self) -> None:
        if not isfinite(self.distance_dip) or self.distance_dip < 0:
            raise ValueError("Snap distance must be finite and nonnegative.")


@dataclass(frozen=True)
class ToolbarDropped:
    position: ScreenPosition
    candidate: SnapCandidate | None = None
    snap_disabled: bool = False


@dataclass(frozen=True)
class DetachClicked:
    position: ScreenPosition


@dataclass(frozen=True)
class AttachedDragged:
    """Raw displacement from drag start, perpendicular to the attached edge.

    Parallel displacement only affects placement. Displacement is measured
    before clamping/snap correction; its sign specifies either normal direction.
    After detachment, dispatch FreeMoved until the final ToolbarDropped.
    """

    target: WindowRef
    perpendicular_dip: float
    position: ScreenPosition
    placement: AttachedPlacement
    maximized: bool = False

    def __post_init__(self) -> None:
        if not isfinite(self.perpendicular_dip):
            raise ValueError("Drag displacement must be finite.")


@dataclass(frozen=True)
class FreeMoved:
    position: ScreenPosition


@dataclass(frozen=True)
class PlacementReset:
    """Reset placement preferences while preserving connection and mode."""


@dataclass(frozen=True)
class TargetClosed:
    target: WindowRef
    last_presented_position: ScreenPosition


@dataclass(frozen=True)
class TargetStateObserved:
    """Refresh presentation separately; native window state is not toolbar mode."""

    window: WindowState


ToolbarEvent = (
    TargetSelected | ToolbarDropped | DetachClicked | AttachedDragged
    | FreeMoved | PlacementReset | TargetClosed | TargetStateObserved
)


@dataclass(frozen=True)
class ReleaseWindowLock:
    """The dispatcher releases this target's lock; reducers never call services."""

    target: WindowRef


@dataclass(frozen=True)
class ToolbarTransition:
    state: ToolbarState
    effects: tuple[ReleaseWindowLock, ...] = ()
