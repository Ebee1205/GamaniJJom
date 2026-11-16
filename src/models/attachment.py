"""Runtime attachment state; geometry is always in native screen pixels."""
from dataclasses import dataclass

from src.models.window_schema import WindowInfo, WindowRect


@dataclass
class Attachment:
    target: WindowInfo
    locked_rect: WindowRect | None = None
    offset: tuple[int, int] = (0, 0)
    hidden: bool = False
    failures: int = 0
