"""Own application lifetime, registry, tray commands and per-target controllers."""
from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QMessageBox, QSystemTrayIcon

from src.services.toolbar_service import PickCancelled
from src.ui.cmp.sys_tray_cmp import SystemTrayComponent
from src.ui.cntr.settings_cntr import SettingsController
from src.ui.cntr.toolbar_cntr import ToolbarController
from src.ui.wd.floating_toolbar import FloatingToolbarWindow


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
        self.settings = SettingsController(windows, attachments, self)
        self.settings.attach_requested.connect(self.show_picker)
        self.settings.target_requested.connect(self.attach)
        self.settings.reveal_requested.connect(self.show_connection)
        self.settings.detach_requested.connect(self.detach)
        self.settings.picker_cancelled.connect(self.cancel_pick)
        self.settings.geometry_changed.connect(self.on_geometry_changed)
        self.settings.notification.connect(self.notify)
        self.tray = SystemTrayComponent(self)
        self.tray.attach_requested.connect(self.show_picker)
        self.tray.settings_requested.connect(self.settings.show)
        self.tray.connection_requested.connect(self.show_connection)
        self.tray.reveal_requested.connect(self.reveal)
        self.tray.quit_requested.connect(app.quit)
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.tick)
        self.pick_timer = QTimer(self)
        self.pick_timer.setInterval(40)
        self.pick_timer.timeout.connect(self.poll_pick)
        self._closed = False
        app.aboutToQuit.connect(self.shutdown)
        self.refresh_views()

    def start(self):
        if self.log is not None:
            self.log.debug("TRAY", f">> Tray startup requested")
        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(None, "GamaniJJom", "시스템 트레이를 사용할 수 없어 종료합니다.")
            return False
        self.tray.show()
        self.timer.start()
        self.show_picker()
        return True

    def notify(self, message):
        self.log.debug("UI", f"<< Notification displayed length={len(message)}")
        self.settings.window.status.setText(message)
        self.tray.showMessage("GamaniJJom", message)

    def refresh_views(self):
        self.settings.refresh()
        self.tray.set_connections(list(self.attachments.attachments.values()))

    def show_picker(self):
        if self.log is not None:
            self.log.debug("TRAY", f">> Target selection requested")
        self.settings.show_picker()
        self.tracking.start_pick()
        self.pick_timer.start()

    def start_pick(self):
        self.show_picker()

    def cancel_pick(self):
        if self.log is not None:
            self.log.debug("TRAY", f">> Target selection cancelled")
        self.tracking.cancel_pick()
        self.pick_timer.stop()

    def poll_pick(self):
        try:
            target = self.tracking.poll_pick()
        except PickCancelled as error:
            if self.log is not None:
                self.log.debug("TRAY", f"<< UI operation ended error_type={type(error).__name__}")
            self.cancel_pick()
            self.settings.picker.hide()
            self.notify(str(error))
            return
        except (OSError, ValueError) as error:
            if self.log is not None:
                self.log.debug("TRAY", f"<< UI operation ended error_type={type(error).__name__}")
            self.settings.picker.status.setText(str(error))
            return
        if target is not None:
            self.attach(target)

    def attach(self, target):
        if self.log is not None:
            self.log.debug("TRAY", f">> Attachment requested hwnd={target.handle_text} pid={target.pid}")
        try:
            attachment = self.attachments.attach(target)
        except (ValueError, OSError) as error:
            if self.log is not None:
                self.log.debug("TRAY", f"<< UI operation ended error_type={type(error).__name__}")
            self.settings.picker.status.setText(str(error))
            self.tracking.start_pick()
            self.pick_timer.start()
            return
        self.cancel_pick()
        self.settings.picker.hide()
        key = attachment.target.identity
        attachment.hidden = False
        if key not in self.controllers:
            window = FloatingToolbarWindow(attachment.target.title)
            controller = ToolbarController(window, attachment, self.locks, self.capture,
                                           self.tracking, self.windows, self)
            controller.notification.connect(self.notify)
            controller.position_requested.connect(self.settings.show_position)
            controller.settings_requested.connect(self.settings.show)
            controller.attach_requested.connect(self.show_picker)
            controller.detach_requested.connect(self.detach)
            controller.changed.connect(self.refresh_views)
            controller.quit_requested.connect(self.app.quit)
            self.controllers[key] = controller
        self.refresh_views()
        self.controllers[key].update()
        self.notify("창을 연결했습니다. 대상 창을 활성화하면 컨트롤러가 표시됩니다.")

    def detach(self, key):
        if self.log is not None:
            self.log.debug("TRAY", f"-- Attachment removal requested hwnd={key[0]} pid={key[1]}")
        controller = self.controllers.pop(key, None)
        if controller:
            controller.dispose()
        self.attachments.detach(key)
        if not self._closed:
            self.refresh_views()

    def reveal(self):
        if self.log is not None:
            self.log.debug("TRAY", f">> Reveal all toolbars requested")
        for controller in list(self.controllers.values()):
            controller.reveal()

    def show_connection(self, key):
        if self.log is not None:
            self.log.debug("TRAY", f">> Reveal connection requested hwnd={key[0]} pid={key[1]}")
        controller = self.controllers.get(key)
        if controller:
            controller.reveal()
            self.notify(f"{controller.attachment.target.title}: 대상 창을 활성화하세요.")

    def on_geometry_changed(self, target):
        controller = self.controllers.get(target.identity)
        if controller:
            controller.sync()
        self.refresh_views()

    def tick(self):
        for controller in list(self.controllers.values()):
            controller.update()

    def shutdown(self):
        if self.log is not None:
            self.log.debug("TRAY", f"- Tray shutdown requested")
        if self._closed:
            return
        self._closed = True
        self.timer.stop()
        self.cancel_pick()
        self.tray.hide()
        self.tray.menu.hide()
        for key in list(self.controllers):
            self.detach(key)
        self.settings.shutdown()
