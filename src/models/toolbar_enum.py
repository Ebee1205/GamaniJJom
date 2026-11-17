"""Toolbar mode and edge enums."""
from enum import Enum

class ToolbarMode(str, Enum):
    FREE = "free"
    ATTACHED = "attached"


class ToolbarEdge(str, Enum):
    TOP = "top"
    RIGHT = "right"
    BOTTOM = "bottom"
    LEFT = "left"