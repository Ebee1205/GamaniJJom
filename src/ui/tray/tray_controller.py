"""Own application lifetime, registry, tray commands and per-target controllers."""
import os

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QMessageBox, QSystemTrayIcon

from src.models.toolbar_event_schema import TargetClosed

from src.ui.tray.tray_widget import TrayWidget
from src.ui.wd_size.wd_size_controller import WdSizeController
from src.ui.toolbar.toolbar_controller import ToolbarController
from src.ui.toolbar.toolbar_window import ToolbarWindow
from src.ui.cmm.cmm_dialog import CmmDialog
from src.ui.settings.setting_dialog import SettingDialog
from src.ui.settings.settings_controller import SettingsController


class TrayController(QObject):
    def __init__(self, app, ctx, windows, attachments, locks, capture, tracking):
        super().__init__(app)
        self.app = app
        self.ctx = ctx
        self.log = ctx.log
        self.windows = windows
        self.attachments = attachments
        self.locks = locks
        self.capture = capture
        self.tracking = tracking
        self.controllers = {}
        self.toolbar_controller = None
        self.programs = WdSizeController(windows, attachments, self)
        self.settings = SettingsController(SettingDialog(self.programs.window), ctx, self)
        self.settings.config_changed.connect(self.apply_settings)
        self.settings.notification.connect(self.notify)
        self.apply_settings()
        self.common_dlg = CmmDialog(self.programs.window, self.log)
        self.common_dlg.rejected.connect(self.cancel_quit)
        self.programs.target_requested.connect(self.attach)
        self.programs.geometry_changed.connect(self.on_geometry_changed)
        self.programs.notification.connect(self.notify)
        self.programs.quit_requested.connect(self.request_quit)
        self.tray = TrayWidget(self)
        self.tray.toolbar_requested.connect(lambda: self.ensure_toolbar().recover_toolbar())
        self.tray.toolbar_mode_requested.connect(self.set_toolbar_mode)
        self.tray.attach_requested.connect(self.show_picker)
        self.tray.programs_requested.connect(self.programs.show)
        self.tray.settings_requested.connect(self.settings.show)
        self.tray.connection_requested.connect(self.show_connection)
        self.tray.quit_requested.connect(self.request_quit)
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.tick)
        self._closed = False
        self._confirming_quit = False
        self._quit_confirmed = False
        app.aboutToQuit.connect(self.shutdown)
        self.refresh_views()

    def start(self):
        if self.log is not None:
            self.log.debug("TRAY", f">> Tray startup requested")
        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(None, "GamaniJJom", "시스템 트레이를 사용할 수 없어 종료합니다.")
            return False
        self.tray.show()
        self.show_picker()
        self.ensure_toolbar().initialize_startup(int(self.programs.window.winId()))
        # Reapply presentation once the initial Qt show/layout events settle.
        # This only reveals the current state, so it cannot reset a selection.
        QTimer.singleShot(0, self.reveal_startup_toolbar)
        self.timer.start()
        return True

    def reveal_startup_toolbar(self):
        if not self._closed and self.toolbar_controller is not None:
            self.toolbar_controller.reveal()

    def apply_settings(self):
        """Refresh shared runtime services after a successful settings save."""
        config = getattr(self.ctx, "cfg", None)
        if config is None:
            return
        self.capture.configure(config.save)
        if self.log is not None:
            self.log.debug("SETTINGS", "!! Runtime settings applied")

    def notify(self, message, *, capture_completed=False):
        self.programs.window.status.setText(message)
        config = getattr(self.ctx, "cfg", None)
        toast_enabled = not capture_completed or config is None or config.save.notification_enabled
        self.log.debug("UI", f"<< Notification processed length={len(message)} toast={toast_enabled}")
        if toast_enabled:
            self.tray.showMessage("GamaniJJom", message)

    def notify_capture(self, message):
        self.notify(message, capture_completed=True)

    def refresh_views(self):
        self.programs.refresh()
        self.tray.set_connections(list(self.attachments.attachments.values()))
        self.update_debug_info()

    def update_debug_info(self):
        toolbar = self.toolbar_controller
        attachments = self.attachments.attachments
        lines = [
            "Application",
            f"  name={self.app.applicationName() or 'GamaniJJom'} pid={os.getpid()}",
            f"  lifecycle={'closing' if self._closed else 'running'} "
            f"quit_confirming={self._confirming_quit} quit_confirmed={self._quit_confirmed}",
            f"  system_tray_available={QSystemTrayIcon.isSystemTrayAvailable()} "
            f"tray_visible={self.tray.isVisible()}",
            f"  program_window_visible={self.programs.window.isVisible()} "
            f"active={self.programs.window.isActiveWindow()}",
            f"  timers=main:{self.timer.isActive()} "
            f"window_refresh:{self.programs.refresh_timer.isActive()} "
            f"position_verify:{self.programs.verify_timer.isActive()}",
            f"  attachments={len(attachments)} controller_registry={len(self.controllers)} "
            f"position_pending={self.programs.pending is not None}",
            "",
            "Toolbar",
        ]

        if toolbar is None:
            lines.append("  controller=not-created")
        else:
            state = toolbar.state
            attachment = toolbar.attachment
            target = attachment.target if attachment is not None else None
            snapshot = toolbar.snapshot
            target_text = (f"{state.target.hwnd:#x} pid={state.target.pid}"
                           if state.target is not None else "none")
            lines.extend((
                f"  controller=created visible={toolbar.window.isVisible()} "
                f"dragging={toolbar.dragging} disposed={toolbar.disposed}",
                f"  status={state.status.value} mode={state.mode.value} connected={state.connected} attached={state.attached}",
                f"  target={target_text} "
                f"title={repr(target.title) if target else '—'}",
                f"  lock={'locked' if attachment and attachment.locked_rect else 'unlocked'} "
                f"locked_rect={attachment.locked_rect if attachment else None}",
                f"  free_position={state.free_position!r}",
                f"  normal_placement={state.normal_placement.edge.value}:"
                f"{state.normal_placement.offset_dip:g}dip "
                f"maximized_placement={state.maximized_placement!r}",
                f"  last_presented={toolbar._last_presented!r}",
                f"  snapshot={self._format_window_snapshot(snapshot)}",
                f"  inspection_error={toolbar._inspection_errors.last!r} "
                f"placement_error={toolbar._placement_errors.last!r}",
            ))

        self.programs.window.set_debug_info("\n".join(lines))

    @staticmethod
    def _format_window_snapshot(snapshot):
        if snapshot is None:
            return "not-observed"
        return (
            f"visible={snapshot.visible} minimized={snapshot.minimized} "
            f"active={snapshot.active} maximized={snapshot.maximized} "
            f"fullscreen={snapshot.fullscreen} title={snapshot.target.title!r}"
        )

    def show_picker(self):
        if self.log is not None:
            self.log.debug("TRAY", f">> Target selection requested")
        self.programs.show_picker()

    def set_toolbar_mode(self, mode):
        try:
            self.ensure_toolbar().switch_renderer(mode)
        except (ValueError, OSError) as error:
            self.notify(str(error))
            actual = self.ensure_toolbar().window.mode
            for action in self.tray.shape_actions.actions():
                action.setChecked(action.data() == actual)

    def ensure_toolbar(self):
        if self.toolbar_controller is None:
            window = ToolbarWindow()
            controller = ToolbarController(window, None, self.locks, self.capture,
                                           self.tracking, self.windows, self)
            controller.notification.connect(self.notify)
            controller.capture_completed.connect(self.notify_capture)
            controller.position_requested.connect(self.programs.show_position)
            controller.settings_requested.connect(self.settings.show)
            controller.attach_requested.connect(self.show_picker)
            controller.connection_changed.connect(self.on_connection_changed)
            controller.changed.connect(self.refresh_views)
            controller.quit_requested.connect(self.request_quit)
            self.toolbar_controller = controller
        return self.toolbar_controller

    def on_connection_changed(self):
        controller = self.toolbar_controller
        self.controllers.clear()
        if controller is not None and controller.attachment is not None:
            self.controllers[controller.attachment.target.identity] = controller
        self.programs.verify_timer.stop()
        self.programs.pending = None
        self.programs.position.set_busy(False)
        self.programs.position.hide()
        if not self._closed:
            self.refresh_views()

    def attach(self, target):
        try:
            controller = self.ensure_toolbar()
            controller.select_target(target)
        except (ValueError, OSError) as error:
            self.notify(str(error))
            return
        if controller.attachment is not None:
            self.programs.window.window_list.select_identity(controller.attachment.target.identity)
        self.refresh_views()

    def detach(self, key):
        # Disconnecting never destroys the singleton toolbar.
        controller = self.toolbar_controller
        if controller is not None and controller.attachment is not None:
            if controller.attachment.target.identity == key:
                controller.dispatch(TargetClosed(controller.state.target, controller.current_position()))
                controller.update()

    def show_connection(self, key):
        if self.log is not None:
            self.log.debug("TRAY", f">> Reveal connection requested hwnd={key[0]} pid={key[1]}")
        controller = self.controllers.get(key)
        if controller:
            controller.reveal()
            self.notify("연결된 프로그램의 컨트롤러를 표시했습니다.")

    def on_geometry_changed(self, target):
        controller = self.controllers.get(target.identity)
        if controller:
            if controller.attachment.locked_rect is None:
                self.locks.release(controller.attachment)
            controller.sync()
        self.refresh_views()

    def tick(self):
        if self.toolbar_controller is not None:
            self.toolbar_controller.update()
        self.update_debug_info()

    def request_quit(self):
        if self._closed or self._confirming_quit or self._quit_confirmed:
            return
        if self.log is not None:
            self.log.debug("UI", ">> Exit confirmation requested")
        self._confirming_quit = True
        self.common_dlg.open_dialog(
            "종료 확인", "종료하시겠습니까?", self.confirm_quit, False, "종료"
        )

    def cancel_quit(self):
        self._confirming_quit = False
        if not self._closed and self.log is not None:
            self.log.debug("UI", "<< Exit cancelled")

    def confirm_quit(self):
        if self._closed or self._quit_confirmed:
            return
        self._confirming_quit = False
        self._quit_confirmed = True
        self.programs.window.exit_confirmed = True
        if self.log is not None:
            self.log.debug("UI", "<< Exit confirmed")
        self.shutdown()
        self.app.quit()

    def shutdown(self):
        if self.log is not None:
            self.log.debug("TRAY", f"- Tray shutdown requested")
        if self._closed:
            return
        self._closed = True
        self.common_dlg.is_active = False
        self.timer.stop()
        self.tray.hide()
        self.tray.menu.hide()
        if self.toolbar_controller is not None:
            self.toolbar_controller.dispose()
        self.controllers.clear()
        self.attachments.attachments.clear()
        self.settings.dispose()
        self.programs.shutdown()
