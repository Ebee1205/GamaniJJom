"""Own application lifetime, registry, tray commands and per-target controllers."""
from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QMessageBox, QSystemTrayIcon

from src.ui.cmp.sys_tray_cmp import SystemTrayComponent
from ui.cntr.wd_size_cntr import WdSizeController
from src.ui.cntr.toolbar_cntr import ToolbarController
from src.ui.wd.floating_toolbar import FloatingToolbarWindow
from src.ui.dlg.common_dlg import CommonDialog


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
        self.settings = WdSizeController(windows, attachments, self)
        self.common_dlg = CommonDialog(self.settings.window, self.log)
        self.common_dlg.rejected.connect(self.cancel_quit)
        self.settings.target_requested.connect(self.attach)
        self.settings.geometry_changed.connect(self.on_geometry_changed)
        self.settings.notification.connect(self.notify)
        self.settings.quit_requested.connect(self.request_quit)
        self.tray = SystemTrayComponent(self)
        self.tray.attach_requested.connect(self.show_picker)
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

    def attach(self, target):
        if self.log is not None:
            self.log.debug("TRAY", f">> Attachment requested hwnd={target.handle_text} pid={target.pid}")
        try:
            attachment = self.attachments.attach(target)
        except (ValueError, OSError) as error:
            if self.log is not None:
                self.log.debug("TRAY", f"<< UI operation ended error_type={type(error).__name__}")
            self.settings.window.status.setText(str(error))
            return
        key = attachment.target.identity
        attachment.hidden = False
        if self.controllers:
            controller = next(iter(self.controllers.values()))
            if controller.attachment.target.identity != key:
                controller.window.toolbar.menu.hide()
                self.settings.verify_timer.stop()
                self.settings.pending = None
                self.settings.position.hide()
                controller.attachment = attachment
                controller.window.setWindowTitle(f"GamaniJJom — {attachment.target.title}")
                controller.sync()
                self.controllers.clear()
                self.controllers[key] = controller
                if self.log is not None:
                    self.log.debug("TRAY", f"!! Controller target changed hwnd={attachment.target.handle_text} pid={attachment.target.pid}")
        else:
            window = FloatingToolbarWindow(attachment.target.title)
            controller = ToolbarController(window, attachment, self.locks, self.capture,
                                           self.tracking, self.windows, self)
            controller.notification.connect(self.notify)
            controller.position_requested.connect(self.settings.show_position)
            controller.settings_requested.connect(self.settings.show)
            controller.attach_requested.connect(self.show_picker)
            controller.detach_requested.connect(self.detach)
            controller.changed.connect(self.refresh_views)
            controller.quit_requested.connect(self.request_quit)
            self.controllers[key] = controller
        self.refresh_views()
        self.controllers[key].update()
        self.settings.window.window_list.select_identity(key)
        self.notify("선택한 프로그램에 컨트롤러를 계속 표시합니다. 다른 프로그램을 연결하면 대상이 변경됩니다.")

    def detach(self, key):
        if self.log is not None:
            self.log.debug("TRAY", f"-- Attachment removal requested hwnd={key[0]} pid={key[1]}")
        controller = self.controllers.pop(key, None)
        if controller:
            controller.dispose()
        self.attachments.detach(key)
        if not self._closed:
            self.refresh_views()

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
            controller.sync()
        self.refresh_views()

    def tick(self):
        for controller in list(self.controllers.values()):
            controller.update()

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
        self.settings.window.exit_confirmed = True
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
        for key in list(self.controllers):
            self.detach(key)
        self.settings.shutdown()
