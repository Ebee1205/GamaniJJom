"""Qt lifetime, target tracking and action routing. No resident main window."""
import os
import time

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from src.adapters.windows import window_api
from src.services.attach_service import AttachService
from src.services.capture_service import CaptureService
from src.services.lock_service import LockService
from src.services.window_service import WindowService
from src.ui.floating_toolbar import FloatingToolbar
from src.ui.main_window import MainWindow
from src.ui.tray import Tray


class DesktopController(QObject):
    def __init__(self, app: QApplication, ctx):
        super().__init__(app)
        self.app = app
        self.ctx = ctx
        self.windows = WindowService()
        self.attachments = AttachService(self.windows)
        self.locks = LockService(self.windows)
        self.capture = CaptureService()
        self.toolbars = {}
        self.picker = MainWindow(self.windows)
        self.picker.target_chosen.connect(self.attach)
        self.picker.geometry_requested.connect(self.geometry_requested)
        self.picker.geometry_applied.connect(self.geometry_applied)
        self.tray = Tray(self)
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.tick)
        self.pick_deadline = 0.0
        self.pick_armed = False
        self.menu = None
        app.aboutToQuit.connect(self.shutdown)

    def start(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        else:
            QMessageBox.critical(None, "GamaniJJom", "시스템 트레이를 사용할 수 없어 종료합니다.")
            return False
        self.timer.start()
        self.show_picker()
        return True

    def notify(self, message):
        self.ctx.log.info("UI", message)
        self.tray.showMessage("GamaniJJom", message)
        self.picker.status.setText(message)

    def show_picker(self):
        self.picker.refresh()
        self.picker.show()
        self.picker.raise_()
        self.picker.activateWindow()

    def start_pick(self):
        self.picker.hide()
        self.pick_deadline = time.monotonic() + 20
        self.pick_armed = False
        self.notify("20초 안에 대상 창을 클릭하세요. Esc로 취소합니다.")

    def poll_pick(self):
        if window_api.key_down(0x1B) or time.monotonic() >= self.pick_deadline:
            self.pick_deadline = 0
            self.notify("대상 선택을 취소했습니다.")
            return
        if not window_api.key_down(0x01):
            self.pick_armed = True
        elif self.pick_armed:
            self.pick_deadline = 0
            try:
                hwnd = window_api.window_at_cursor()
                target = window_api.read_window(hwnd)
                if target.pid == os.getpid() or not target.title.strip():
                    raise ValueError("연결할 프로그램의 일반 창을 선택하세요.")
                self.attach(target)
            except (ValueError, OSError) as error:
                self.notify(str(error))

    def attach(self, target):
        try:
            attachment = self.attachments.attach(target)
        except OSError as error:
            self.notify(str(error))
            return
        key = attachment.target.identity
        attachment.hidden = False
        if key not in self.toolbars:
            toolbar = FloatingToolbar(attachment.target.title)
            self.toolbars[key] = toolbar
            toolbar.lock_requested.connect(lambda: self.toggle_lock(key))
            toolbar.capture_requested.connect(lambda: self.capture_target(key))
            toolbar.more_requested.connect(lambda: self.show_more(key))
            toolbar.dragged.connect(lambda dx, dy: self.drag(key, dx, dy))
        self.picker.hide()
        self.notify("창을 연결했습니다. 대상 창을 활성화하면 컨트롤러가 표시됩니다.")
        self.tick()

    def detach(self, key):
        toolbar = self.toolbars.pop(key, None)
        if toolbar:
            toolbar.hide()
            toolbar.deleteLater()
        self.attachments.detach(key)

    def toggle_lock(self, key):
        attachment = self.attachments.attachments.get(key)
        if not attachment:
            return
        try:
            self.locks.toggle(attachment)
        except (ValueError, OSError) as error:
            self.notify(str(error))
        self.toolbars[key].sync_lock(attachment.locked_rect is not None)

    def geometry_applied(self, current):
        attachment = self.attachments.attachments.get(current.identity)
        if attachment and attachment.locked_rect is not None:
            # Explicit geometry edits become the new lock target.
            attachment.locked_rect = current.rect
            attachment.failures = 0

    def geometry_requested(self, target):
        attachment = self.attachments.attachments.get(target.identity)
        if attachment:
            # Stop the old lock before an asynchronous explicit geometry edit.
            attachment.locked_rect = None
            self.toolbars[target.identity].sync_lock(False)

    def capture_target(self, key):
        attachment = self.attachments.attachments.get(key)
        if attachment:
            try:
                self.capture.capture(self.windows.read(attachment.target))
            except (NotImplementedError, OSError) as error:
                self.notify(str(error))

    def drag(self, key, dx, dy):
        attachment = self.attachments.attachments.get(key)
        if attachment:
            scale = self.toolbars[key].devicePixelRatioF()
            x, y = attachment.offset
            attachment.offset = (x + round(dx * scale), y + round(dy * scale))
            self.tick()

    def reveal(self):
        for attachment in self.attachments.attachments.values():
            attachment.hidden = False
        self.tick()

    def show_connection(self, key):
        attachment = self.attachments.attachments.get(key)
        if attachment:
            attachment.hidden = False
            self.notify(f"{attachment.target.title}: 대상 창을 활성화하세요.")

    def hide_connection(self, key):
        attachment = self.attachments.attachments.get(key)
        if attachment:
            attachment.hidden = True
            self.toolbars[key].hide()

    def reset_position(self, key):
        attachment = self.attachments.attachments.get(key)
        if attachment:
            attachment.offset = (0, 0)

    def show_more(self, key):
        self.menu = QMenu()
        self.menu.addAction("프로그램 연결…", self.show_picker)
        self.menu.addAction("좌표·크기 설정…", self.show_picker)
        self.menu.addAction("부착 위치 초기화", lambda: self.reset_position(key))
        self.menu.addAction("툴바 숨기기", lambda: self.hide_connection(key))
        self.menu.addAction("연결 해제 (Lock 해제)", lambda: self.detach(key))
        self.menu.addSeparator()
        self.menu.addAction("종료", self.app.quit)
        self.menu.popup(QCursor.pos())

    def tick(self):
        if self.pick_deadline:
            self.poll_pick()
        foreground = window_api.foreground_window()
        for key, attachment in list(self.attachments.attachments.items()):
            toolbar = self.toolbars[key]
            try:
                # Read identity even when the target is hidden; don't reuse an HWND.
                current = window_api.read_window(attachment.target.hwnd)
                if current.identity != key:
                    raise OSError("대상 창의 프로세스가 변경되었습니다.")
            except OSError:
                self.detach(key)
                continue
            attachment.target = current
            if not window_api.is_visible(current.hwnd):
                toolbar.hide()
                continue
            try:
                self.locks.enforce(attachment, current)
            except (ValueError, OSError) as error:
                attachment.locked_rect = None
                self.notify(f"Lock 해제: {error}")
            toolbar.sync_lock(attachment.locked_rect is not None)
            try:
                fullscreen = current.rect == window_api.monitor_bounds(current.hwnd, work=False)
            except OSError:
                toolbar.hide()
                continue
            if (attachment.hidden or window_api.is_minimized(current.hwnd)
                    or fullscreen or foreground != current.hwnd):
                toolbar.hide()
                continue
            try:
                self.place_toolbar(toolbar, current, attachment.offset)
                toolbar.show()
            except OSError as error:
                toolbar.hide()
                self.ctx.log.warning("UI", f"툴바 배치 실패: {error}")

    @staticmethod
    def place_toolbar(toolbar, target, offset):
        handle = int(toolbar.winId())
        native = window_api.read_window(handle).rect
        area = window_api.monitor_bounds(target.hwnd)
        r = target.rect
        x = r.x + r.width - native.width + offset[0]
        y = r.y - native.height + offset[1]
        x = max(area.x, min(x, area.x + area.width - native.width))
        y = max(area.y, min(y, area.y + area.height - native.height))
        window_api.place_toolbar(handle, x, y)

    def shutdown(self):
        self.timer.stop()
        self.pick_deadline = 0
        self.tray.hide()
        for key in list(self.toolbars):
            self.detach(key)
        self.picker.hide()
