"""Data shared between the UI, services, and Windows adapter."""
from dataclasses import dataclass


@dataclass(frozen=True)
class WindowRect:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    pid: int
    title: str
    rect: WindowRect

    @property
    def handle_text(self) -> str:
        """HWND as shown to the user, e.g. 0x1A2B."""
        return f"0x{self.hwnd:X}"

    @property
    def identity(self) -> tuple[int, int]:
        """(hwnd, pid). An HWND can be reused by another process after its window closes."""
        return (self.hwnd, self.pid)