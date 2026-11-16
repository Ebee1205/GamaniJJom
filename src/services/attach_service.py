"""One controller per (HWND, PID); no automatic reconnection to recycled handles."""
from src.models.attachment import Attachment
from src.models.window_schema import WindowInfo
from src.services.window_service import WindowService


class AttachService:
    def __init__(self, windows: WindowService):
        self.windows = windows
        self.attachments: dict[tuple[int, int], Attachment] = {}

    def attach(self, target: WindowInfo) -> Attachment:
        current = self.windows.read(target)
        return self.attachments.setdefault(current.identity, Attachment(current))

    def detach(self, identity: tuple[int, int]) -> None:
        self.attachments.pop(identity, None)
