"""Win32 enum values shared by window adapters and services."""
from enum import IntEnum, IntFlag


class WindowLongIndex(IntEnum):
    EXTENDED_STYLE = -20


class GetWindowCommand(IntEnum):
    OWNER = 4


class WindowExtendedStyle(IntFlag):
    TOOLWINDOW = 0x00000080
    APPWINDOW = 0x00040000


class DwmWindowAttribute(IntEnum):
    CLOAKED = 14


class DpiAwarenessContext(IntEnum):
    PER_MONITOR_AWARE_V2 = -4


class SetWindowPosFlag(IntFlag):
    NOMOVE = 0x0002
    NOZORDER = 0x0004
    NOACTIVATE = 0x0010
    NOSIZE = 0x0001
    ASYNCWINDOWPOS = 0x4000


class WindowMessage(IntEnum):
    CANCELMODE = 0x001F


class GuiThreadFlag(IntFlag):
    INMOVESIZE = 0x00000002