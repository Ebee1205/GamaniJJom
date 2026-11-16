"""Keep exactly one explicit target; validate replacements before releasing it."""
from src.models.attachment import Attachment
from src.models.window_schema import WindowInfo
from src.services.window_service import WindowService


class AttachService:
    def __init__(self, windows: WindowService):
        self.windows = windows
        self.attachments: dict[tuple[int, int], Attachment] = {}

    def attach(self, target: WindowInfo) -> Attachment:
        current = self.windows.read(target)
        existing = self.attachments.get(current.identity)
        if existing is not None:
            return existing
        for attachment in self.attachments.values():
            attachment.locked_rect = None
            attachment.failures = 0
        self.attachments.clear()
        attachment = Attachment(current)
        self.attachments[current.identity] = attachment
        return attachment

    def detach(self, identity: tuple[int, int]) -> None:
        self.attachments.pop(identity, None)
