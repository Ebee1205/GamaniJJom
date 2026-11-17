"""Data shared between the UI, services, and Windows adapter."""
from dataclasses import dataclass


@dataclass(frozen=True)
class WindowRef:
    """Runtime window identity, independent of its changing title and bounds."""

    hwnd: int
    pid: int

    @property
    def identity(self) -> tuple[int, int]:
        return self.hwnd, self.pid


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
    def reference(self) -> WindowRef:
        return WindowRef(self.hwnd, self.pid)

    @property
    def handle_text(self) -> str:
        """HWND as shown to the user, e.g. 0x1A2B."""
        return f"0x{self.hwnd:X}"

    @property
    def identity(self) -> tuple[int, int]:
        """(hwnd, pid). An HWND can be reused by another process after its window closes."""
        return (self.hwnd, self.pid)


@dataclass(frozen=True)
class WindowState:
    """One observation of a target window; rect uses native screen pixels.

    Maximized and fullscreen are separate observations. Neither changes the
    toolbar's attachment mode. This model is runtime data, not saved config.
    ``active`` includes the toolbar's interaction window for legacy tracking.
    """

    target: WindowInfo
    visible: bool
    minimized: bool
    active: bool
    fullscreen: bool
    maximized: bool = False

    @property
    def show_toolbar(self) -> bool:
        """Legacy attached-toolbar visibility until presentation is migrated."""
        return self.visible and not self.minimized
