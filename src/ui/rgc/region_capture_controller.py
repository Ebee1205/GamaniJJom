"""Manage capture region state and coordinate it with the selection dialog."""
from dataclasses import replace

from PySide6.QtCore import QObject, Signal

from src.ui.rgc.region_capture_dialog import MIN_SIZE, RegionCaptureDialog


def _move(rect, dx, dy):
    return replace(rect, x=rect.x + dx, y=rect.y + dy)


class RegionCaptureController(QObject):
    """Keep the chosen rectangle relative to the current target's top-left."""
    capture_requested = Signal()
    notification = Signal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.rect = None
        self.selecting = False
        self._suspended = False
        self._target = None
        self._target_rect = None
        self._target_visible = True
        self._size_locked = False
        self._dialog = RegionCaptureDialog()
        self._dialog.preview.connect(self._present)
        self._dialog.finished.connect(self._finish_selection)
        self._dialog.capture_requested.connect(self.capture_requested.emit)
        self._dialog.clear_requested.connect(self.clear)
        self._dialog.lock_requested.connect(self._set_size_locked)
        self._dialog.moved.connect(self._move_region)
        self._dialog.resized.connect(self._resize_region)
        self._dialog.size_requested.connect(self._set_size)

    def start(self):
        if self.selecting:
            return
        self.selecting = True
        self._present(None)
        try:
            self._dialog.begin()
        except OSError as error:
            self._finish_selection(None)
            self.notification.emit(str(error))

    def cancel_selection(self):
        if self.selecting:
            self._finish_selection(None)

    def _finish_selection(self, rect):
        self._dialog.end()
        if rect is not None:
            origin = self._target_rect
            self.rect = _move(rect, -origin.x, -origin.y) if origin else rect
            self._size_locked = False
        self.selecting = False
        self.refresh()

    def clear(self):
        self.rect = None
        self._size_locked = False
        self.refresh()

    def observe(self, target, *, visible=True):
        origin = target.rect if target is not None else None
        reference = target.reference if target is not None else None
        if (reference, origin, visible) == (self._target, self._target_rect, self._target_visible):
            return
        # Preserve the last screen position on disconnect or a target switch.
        if self.rect is not None and reference != self._target:
            rect = self.screen_rect
            self.rect = _move(rect, -origin.x, -origin.y) if origin else rect
        self._target, self._target_rect, self._target_visible = reference, origin, visible
        if not self.selecting:
            self.refresh()

    @property
    def screen_rect(self):
        origin = self._target_rect
        return _move(self.rect, origin.x, origin.y) if self.rect and origin else self.rect

    def capture_rect(self):
        if not self._target_visible:
            raise OSError('연결된 창을 화면에 표시한 뒤 영역을 캡처하세요.')
        return self.screen_rect

    def set_suspended(self, suspended):
        self._suspended = suspended
        self.refresh()

    def refresh(self):
        if not self.selecting:
            self._present(self.screen_rect if self._target_visible and not self._suspended else None)

    def _move_region(self, dx, dy):
        if self.rect is not None:
            self.rect = _move(self.rect, dx, dy)
            self.refresh()

    def _resize_region(self, dx, dy):
        if self.rect is not None:
            self._set_size(max(MIN_SIZE, self.rect.width + dx),
                           max(MIN_SIZE, self.rect.height + dy))

    def _set_size(self, width, height):
        if self.rect is not None and not self._size_locked and not self.selecting:
            self.rect = replace(self.rect, width=width, height=height)
            self.refresh()

    def _set_size_locked(self, locked):
        self._size_locked = locked
        self.refresh()

    def _present(self, rect):
        try:
            self._dialog.present(rect, selecting=self.selecting,
                                 follows_window=self._target is not None, locked=self._size_locked)
        except OSError as error:
            self._dialog.hide_preview()
            self.notification.emit(str(error))

    def dispose(self):
        self._dialog.dispose()
