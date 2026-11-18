"""Pure toolbar policy: reduce intent, returning deferred lock-release commands.

The dispatcher validates targets, calls reduce_toolbar, applies effects to the
previous connection, then commits state and updates presentation. No effects
are executed here. Existing UI/Attachment lifecycle is migrated separately.
"""
from dataclasses import replace

from src.models.toolbar_enum import ToolbarMode
import src.models.toolbar_event_schema as toolbar_event_schema
from src.models.toolbar_schema import AttachedPlacement, ToolbarState
from src.models.window_schema import WindowRef


SNAP_DISTANCE_DIP = 24.0
DETACH_DISTANCE_DIP = 48.0


def _release_previous(
    state: ToolbarState,
    target: WindowRef | None,
) -> tuple[toolbar_event_schema.ReleaseWindowLock, ...]:
    if state.target is not None and state.target != target:
        return (toolbar_event_schema.ReleaseWindowLock(state.target),)
    return ()


def reduce_toolbar(
    state: ToolbarState,
    event: toolbar_event_schema.ToolbarEvent,
) -> toolbar_event_schema.ToolbarTransition:
    """Return new immutable intent and commands, without observing native windows.

    Selection preserves the toolbar's existing edge/offset preferences. A snap
    explicitly replaces the placement for the candidate's current window mode.
    Non-candidate layout, lock and position data are never inferred from HWNDs.
    """
    if isinstance(event, toolbar_event_schema.TargetSelected):
        if event.target == state.target:
            return toolbar_event_schema.ToolbarTransition(state)
        return toolbar_event_schema.ToolbarTransition(
            replace(state, target=event.target, free_anchor=None,
                    free_position=event.position or state.free_position),
            _release_previous(state, event.target),
        )

    if isinstance(event, toolbar_event_schema.TargetPicked):
        candidate = event.candidate
        attached = replace(state, mode=ToolbarMode.ATTACHED, target=candidate.target,
                           free_anchor=None)
        attached = (replace(attached, maximized_placement=candidate.placement)
                    if candidate.maximized else replace(attached, normal_placement=candidate.placement))
        return toolbar_event_schema.ToolbarTransition(attached, _release_previous(state, candidate.target))

    if isinstance(event, toolbar_event_schema.FreeAnchorSet):
        if state.attached or event.target != state.target or state.target is None:
            return toolbar_event_schema.ToolbarTransition(state)
        return toolbar_event_schema.ToolbarTransition(replace(state, free_anchor=event.anchor))

    if isinstance(event, toolbar_event_schema.ToolbarDropped):
        # A still-attached drag must first cross 48 DIP to change targets.
        if state.attached:
            return toolbar_event_schema.ToolbarTransition(state)
        candidate = event.candidate
        if (event.snap_disabled or candidate is None
                or candidate.distance_dip > SNAP_DISTANCE_DIP):
            return toolbar_event_schema.ToolbarTransition(
                replace(state, free_position=event.position, free_anchor=None)
            )
        attached = replace(state, mode=ToolbarMode.ATTACHED, target=candidate.target, free_anchor=None)
        attached = (replace(attached, maximized_placement=candidate.placement)
                    if candidate.maximized
                    else replace(attached, normal_placement=candidate.placement))
        return toolbar_event_schema.ToolbarTransition(
            attached,
            _release_previous(state, candidate.target),
        )

    if isinstance(event, toolbar_event_schema.DetachClicked):
        if not state.attached:
            return toolbar_event_schema.ToolbarTransition(state)
        return toolbar_event_schema.ToolbarTransition(
            replace(state, mode=ToolbarMode.FREE, free_position=event.position, free_anchor=None),
        )

    if isinstance(event, toolbar_event_schema.AttachedDragged):
        if not state.attached or event.target != state.target:
            return toolbar_event_schema.ToolbarTransition(state)
        if abs(event.perpendicular_dip) >= DETACH_DISTANCE_DIP:
            return toolbar_event_schema.ToolbarTransition(
                replace(state, mode=ToolbarMode.FREE, free_position=event.position, free_anchor=None),
            )
        adjusted = (replace(state, maximized_placement=event.placement)
                    if event.maximized
                    else replace(state, normal_placement=event.placement))
        return toolbar_event_schema.ToolbarTransition(adjusted)

    if isinstance(event, toolbar_event_schema.FreeMoved):
        if state.attached:
            return toolbar_event_schema.ToolbarTransition(state)
        return toolbar_event_schema.ToolbarTransition(replace(state, free_position=event.position, free_anchor=None))

    if isinstance(event, toolbar_event_schema.PlacementReset):
        return toolbar_event_schema.ToolbarTransition(
            replace(
                state,
                normal_placement=AttachedPlacement(),
                maximized_placement=None,
                free_position=None,
                free_anchor=None,
            )
        )

    if isinstance(event, toolbar_event_schema.TargetClosed):
        if event.target != state.target:
            return toolbar_event_schema.ToolbarTransition(state)
        position = (event.last_presented_position if state.attached or state.free_anchor is not None
                    else state.free_position or event.last_presented_position)
        return toolbar_event_schema.ToolbarTransition(
            replace(state, mode=ToolbarMode.FREE, target=None, free_position=position, free_anchor=None),
            _release_previous(state, None),
        )

    if isinstance(event, toolbar_event_schema.TargetStateObserved):
        # Minimize, restore, maximize, fullscreen, focus and visibility belong to
        # the window snapshot/presentation layer. Never reconnect on observation.
        return toolbar_event_schema.ToolbarTransition(state)

    raise TypeError(f"Unsupported toolbar event: {type(event).__name__}")
