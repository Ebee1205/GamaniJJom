"""Win32 enum values shared by window adapters and services."""
from enum import IntEnum, IntFlag


class WindowLongIndex(IntEnum):
    STYLE = -16
    EXTENDED_STYLE = -20


class WindowStyle(IntFlag):
    CAPTION = 0x00C00000
    THICKFRAME = 0x00040000


class WindowEvent(IntEnum):
    FOREGROUND = 0x0003
    MINIMIZE_START = 0x0016
    MINIMIZE_END = 0x0017
    DESTROY = 0x8001
    SHOW = 0x8002
    HIDE = 0x8003
    STATE_CHANGE = 0x800A
    LOCATION_CHANGE = 0x800B
    NAME_CHANGE = 0x800C
    CLOAKED = 0x8017
    UNCLOAKED = 0x8018


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
