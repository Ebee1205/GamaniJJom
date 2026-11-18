"""Toolbar mode and edge enums."""
from enum import Enum

class ToolbarMode(str, Enum):
    FREE = "free"
    ATTACHED = "attached"


class ToolbarStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED_FREE = "connected_free"
    ATTACHED = "attached"


class ToolbarEdge(str, Enum):
    TOP = "top"
    RIGHT = "right"
    BOTTOM = "bottom"
    LEFT = "left"

class CaptureMode(str, Enum):
    WINDOW = "window"
    PRIMARY_SCREEN = "primary_screen"
