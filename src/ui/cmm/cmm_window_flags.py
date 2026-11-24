"""Window flag profiles for toolbars, floating controls, and overlays."""
from PySide6.QtCore import Qt

_TOOL = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
_TOPMOST_TOOL = _TOOL | Qt.WindowType.WindowStaysOnTopHint
_FLOATING_TOOL = _TOPMOST_TOOL | Qt.WindowType.NoDropShadowWindowHint
_NO_FOCUS = Qt.WindowType.WindowDoesNotAcceptFocus

# Keep the toolbar activation and stacking policies independent.
TOOLBAR_WINDOW_FLAGS = _TOOL | _NO_FOCUS

# The picker and region input controls must still accept keyboard focus.
PICKER_WINDOW_FLAGS = _TOPMOST_TOOL
RADIAL_MENU_WINDOW_FLAGS = _FLOATING_TOOL
REGION_WINDOW_FLAGS = _FLOATING_TOOL
REGION_GRIP_WINDOW_FLAGS = _FLOATING_TOOL | _NO_FOCUS

# Preview overlays must also let mouse input pass through.
OVERLAY_WINDOW_FLAGS = (
    _FLOATING_TOOL | _NO_FOCUS | Qt.WindowType.WindowTransparentForInput
)
