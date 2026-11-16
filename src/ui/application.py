"""Composition root. Native API access stays behind services."""
from src.services.attach_service import AttachService
from src.services.capture_service import CaptureService
from src.services.lock_service import LockService
from src.services.toolbar_service import ToolbarService
from src.services.window_service import WindowService
from src.ui.tray.tray_controller import TrayController


class DesktopController(TrayController):
    def __init__(self, app, ctx):
        windows = WindowService()
        super().__init__(app, ctx, windows, AttachService(windows),
                         LockService(windows), CaptureService(ctx.cfg.save.path, ctx.log), ToolbarService())
