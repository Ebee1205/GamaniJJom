"""Pure toolbar policy: reduce intent, returning deferred lock-release commands.

The dispatcher validates targets, calls reduce_toolbar, applies effects to the
previous connection, then commits state and updates presentation. No effects
are executed here. Existing UI/Attachment lifecycle is migrated separately.
"""
from dataclasses import replace

from src.models.toolbar_enum import ToolbarMode
from src.models.toolbar_event_schema import (
    AttachedDragged, DetachClicked, FreeMoved, PlacementReset, ReleaseWindowLock,
    TargetClosed, TargetSelected, TargetStateObserved, ToolbarDropped,
    ToolbarEvent, ToolbarTransition,
)
from src.models.toolbar_schema import AttachedPlacement, ToolbarState
from src.models.window_schema import WindowRef


SNAP_DISTANCE_DIP = 24.0
DETACH_DISTANCE_DIP = 48.0


def _release_previous(state: ToolbarState, target: WindowRef | None) -> tuple[ReleaseWindowLock, ...]:
    if state.target is not None and state.target != target:
        return (ReleaseWindowLock(state.target),)
    return ()


def reduce_toolbar(state: ToolbarState, event: ToolbarEvent) -> ToolbarTransition:
    """Return new immutable intent and commands, without observing native windows.

    Selection preserves the toolbar's existing edge/offset preferences. A snap
    explicitly replaces the placement for the candidate's current window mode.
    Non-candidate layout, lock and position data are never inferred from HWNDs.
    """
    if isinstance(event, TargetSelected):
        if event.target == state.target:
            return ToolbarTransition(state)
        return ToolbarTransition(
            replace(state, target=event.target),
            _release_previous(state, event.target),
        )

    if isinstance(event, ToolbarDropped):
        # A still-attached drag must first cross 48 DIP to change targets.
        if state.attached:
            return ToolbarTransition(state)
        candidate = event.candidate
        if (event.snap_disabled or candidate is None
                or candidate.distance_dip > SNAP_DISTANCE_DIP):
            return ToolbarTransition(replace(state, free_position=event.position))
        attached = replace(state, mode=ToolbarMode.ATTACHED, target=candidate.target)
        attached = (replace(attached, maximized_placement=candidate.placement)
                    if candidate.maximized
                    else replace(attached, normal_placement=candidate.placement))
        return ToolbarTransition(
            attached,
            _release_previous(state, candidate.target),
        )

    if isinstance(event, DetachClicked):
        if not state.attached:
            return ToolbarTransition(state)
        return ToolbarTransition(
            replace(state, mode=ToolbarMode.FREE, free_position=event.position),
        )

    if isinstance(event, AttachedDragged):
        if not state.attached or event.target != state.target:
            return ToolbarTransition(state)
        if abs(event.perpendicular_dip) >= DETACH_DISTANCE_DIP:
            return ToolbarTransition(
                replace(state, mode=ToolbarMode.FREE, free_position=event.position),
            )
        adjusted = (replace(state, maximized_placement=event.placement)
                    if event.maximized
                    else replace(state, normal_placement=event.placement))
        return ToolbarTransition(adjusted)

    if isinstance(event, FreeMoved):
        if state.attached:
            return ToolbarTransition(state)
        return ToolbarTransition(replace(state, free_position=event.position))

    if isinstance(event, PlacementReset):
        return ToolbarTransition(replace(state, normal_placement=AttachedPlacement(),
                                         maximized_placement=None, free_position=None))

    if isinstance(event, TargetClosed):
        if event.target != state.target:
            return ToolbarTransition(state)
        position = (event.last_presented_position if state.attached
                    else state.free_position or event.last_presented_position)
        return ToolbarTransition(
            replace(state, mode=ToolbarMode.FREE, target=None, free_position=position),
            _release_previous(state, None),
        )

    if isinstance(event, TargetStateObserved):
        # Minimize, restore, maximize, fullscreen, focus and visibility belong to
        # the window snapshot/presentation layer. Never reconnect on observation.
        return ToolbarTransition(state)

    raise TypeError(f"Unsupported toolbar event: {type(event).__name__}")
