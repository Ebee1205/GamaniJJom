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
