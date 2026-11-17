"""Observe a selected window independently of Window Lock.

Install and close on the Qt message-loop thread. Callbacks only enqueue a
notification; consumers reread native state instead of treating events as facts.
"""
import ctypes
from ctypes import wintypes as wt
from dataclasses import dataclass

from src.adapters.windows import window_api as api
from src.models.window_enum import WindowEvent
from src.models.window_schema import WindowRef


WinEventProc = ctypes.WINFUNCTYPE(
    None, wt.HANDLE, wt.DWORD, wt.HWND, wt.LONG, wt.LONG, wt.DWORD, wt.DWORD,
)
install_event = api._bind(api.user32, "SetWinEventHook",
                        [wt.DWORD, wt.DWORD, wt.HMODULE, WinEventProc,
                         wt.DWORD, wt.DWORD, wt.DWORD], wt.HANDLE)
remove_event = api._bind(api.user32, "UnhookWinEvent", [wt.HANDLE], wt.BOOL)
# Keep ctypes callbacks alive if Windows unexpectedly refuses to unhook them.
_pending_cleanup = set()


@dataclass(frozen=True)
class WindowChange:
    event: WindowEvent
    target: WindowRef
    generation: int


class WindowEventWatcher:
    def __init__(self, on_change):
        self.on_change = on_change
        self.target = None
        self.generation = 0
        self.handles = []
        self.error = None
        self._installed = False
        self.callback = WinEventProc(self._dispatch)

    def watch(self, target: WindowRef) -> None:
        if target != self.target:
            self.generation += 1
            self.target = target
        if self._installed:
            return
        if self.handles:
            raise OSError("Previous window event hooks could not be removed.")
        try:
            for event in WindowEvent:
                handle = install_event(event, event, None, self.callback, 0, 0, 0)
                if not handle:
                    raise api._last_error()
                self.handles.append(handle)
            self._installed = True
        except OSError:
            self.close()
            raise

    def close(self) -> None:
        self._installed = False
        self.target = None
        self.generation += 1
        remaining = []
        for handle in self.handles:
            if not remove_event(handle):
                remaining.append(handle)
                self.error = api._last_error()
        self.handles = remaining
        if remaining:
            _pending_cleanup.add(self)
        else:
            _pending_cleanup.discard(self)

    def _dispatch(self, _hook, event, hwnd, object_id, child_id, _thread, _time):
        target = self.target
        if target is None:
            return
        try:
            kind = WindowEvent(event)
            if kind != WindowEvent.FOREGROUND:
                if hwnd != target.hwnd or object_id != 0 or child_id != 0:
                    return
            # Destroyed HWNDs cannot be queried safely. Consumers revalidate
            # identity on the UI thread, including for delayed destroy events.
            self.on_change(WindowChange(kind, target, self.generation))
        except Exception as error:
            # Exceptions must not escape a ctypes callback.
            self.error = error
