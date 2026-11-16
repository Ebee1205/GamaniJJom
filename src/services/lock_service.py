"""Enforce captured geometry without restoring minimized/maximized windows."""
from src.models.attachment import Attachment
from src.models.window_schema import WindowInfo
from src.services.window_service import WindowService


class LockService:
    def __init__(self, windows: WindowService):
        self.windows = windows

    def toggle(self, attachment: Attachment) -> bool:
        if attachment.locked_rect is not None:
            attachment.locked_rect = None
            attachment.failures = 0
            return False
        current = self.windows.read(attachment.target)
        if self.windows.is_suspended(current):
            raise ValueError("일반 창으로 복원한 뒤 Lock을 켜세요.")
        attachment.locked_rect = current.rect
        attachment.failures = 0
        return True

    def enforce(self, attachment: Attachment, current: WindowInfo) -> bool:
        desired = attachment.locked_rect
        if desired is None or self.windows.is_suspended(current):
            return False
        if desired == current.rect:
            attachment.failures = 0
            return False
        # Asynchronous requests may be accepted but ignored by the other app.
        # Stop after five unsuccessful observations rather than fight indefinitely.
        attachment.failures += 1
        if attachment.failures > 5:
            attachment.locked_rect = None
            raise OSError("창이 고정 요청을 따르지 않아 Lock을 해제했습니다.")
        self.windows.apply(current, desired)
        return True
