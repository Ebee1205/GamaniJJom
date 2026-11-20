"""Manage the unified program list and the existing geometry dialog."""
from PySide6.QtCore import QObject, QTimer, Qt, Signal

from src.services.window_service import _validate_rect
from src.ui.cmm.cmm_dialog_layout import show_dialog
from src.ui.wd_size.wd_size_dialog import WdSizeDialog
from src.ui.programs_window import ProgramsWindow


class WdSizeController(QObject):
    target_requested = Signal(object)
    geometry_changed = Signal(object)
    notification = Signal(str)

    def __init__(self, windows, attachments, parent=None, *, dialog_parent=None):
        super().__init__(parent)
        self.log = parent.ctx.log if parent is not None else None
        self.windows = windows
        self.attachments = attachments
        self.window = ProgramsWindow()
        self.position = WdSizeDialog(dialog_parent)
        self.window.log = self.log
        self.position.log = self.log
        self.window.window_list.log = self.log
        self.window.available_list.log = self.log
        self.pending = None
        self.verify_timer = QTimer(self)
        self.verify_timer.setSingleShot(True)
        self.verify_timer.timeout.connect(self.verify)
        self.window.position_requested.connect(self.show_position)
        self.window.target_requested.connect(self.target_requested.emit)
        self.window.refresh_requested.connect(self.refresh)
        self.position.apply_requested.connect(self.apply_position)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1000)
        self.refresh_timer.timeout.connect(self.refresh_visible)
        self.refresh_timer.start()

    @staticmethod
    def open(window):
        if window.isMinimized():
            window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized)
        window.show()
        window.raise_()
        window.activateWindow()

    def show(self):
        if self.log is not None:
            self.log.debug("UI", ">> Main program list requested")
        self.refresh()
        self.open(self.window)

    def refresh(self):
        if self.log is not None:
            self.log.debug("SETTINGS", f"== Attachment list refresh requested")
        attachments = list(self.attachments.attachments.values())
        statuses = {a.target.identity: ("Lock" if a.locked_rect else "미고정")
                    + (" · 숨김" if a.hidden else "") for a in attachments}
        offsets = {a.target.identity: f"{a.offset[0]}, {a.offset[1]}" for a in attachments}
        self.window.window_list.set_windows([a.target for a in attachments], statuses, offsets,
                                          connected_identities=self.attachments.attachments)
        self.window.connected_count.setText(f"{len(attachments)}개")
        self.refresh_picker()

    def refresh_visible(self):
        if self.window.isVisible():
            self.refresh()

    def refresh_picker(self):
        if self.log is not None:
            self.log.debug("SETTINGS", f"== Available window list refresh requested")
        try:
            windows = self.windows.list_windows()
            attached = self.attachments.attachments
            statuses = {window.identity: "연결됨" if window.identity in attached else "미연결" for window in windows}
            self.window.available_list.set_windows(windows, statuses, connected_identities=attached)
            self.window.all_count.setText(f"{len(windows)}개")
        except OSError as error:
            if self.log is not None:
                self.log.debug("SETTINGS", f"<< UI operation ended error_type={type(error).__name__}")
            self.window.status.setText(str(error))

    def show_position(self, target):
        if self.log is not None:
            self.log.debug("SETTINGS", f">> Position dialog requested hwnd={target.handle_text} pid={target.pid}")
        if self.pending is not None:
            show_dialog(self.position)
            self.position.status.setText("이전 변경 결과를 확인하는 중입니다.")
            return
        try:
            current = self.windows.read(target)
        except OSError as error:
            if self.log is not None:
                self.log.debug("SETTINGS", f"<< UI operation ended error_type={type(error).__name__}")
            self.notification.emit(str(error))
            return
        self.position.set_target(current)
        show_dialog(self.position)

    def apply_position(self, rect):
        if self.log is not None:
            self.log.debug("SETTINGS", f">> Position apply requested x={rect.x} y={rect.y} width={rect.width} height={rect.height}")
        target = self.position.target
        if self.pending is not None or target is None:
            return
        try:
            _validate_rect(rect)
            self.windows.read(target)
            if self.windows.is_suspended(target):
                raise ValueError("일반 창으로 복원한 뒤 적용하세요.")
            attachment = self.attachments.attachments.get(target.identity)
            if attachment:
                attachment.locked_rect = None
                attachment.failures = 0
                self.geometry_changed.emit(target)
            self.windows.apply(target, rect)
        except (ValueError, OSError) as error:
            if self.log is not None:
                self.log.debug("SETTINGS", f"<< UI operation ended error_type={type(error).__name__}")
            self.position.status.setText(f"적용 실패: {error}")
            return
        self.pending = target, rect
        self.position.set_busy(True)
        self.position.status.setText("변경 요청을 보냈습니다. 실제 결과 확인 중…")
        self.verify_timer.start(300)

    def verify(self):
        if self.log is not None:
            self.log.debug("SETTINGS", f"== Position verification requested")
        if self.pending is None:
            return
        target, requested = self.pending
        self.pending = None
        try:
            current = self.windows.read(target)
        except OSError as error:
            if self.log is not None:
                self.log.debug("SETTINGS", f"<< UI operation ended error_type={type(error).__name__}")
            self.position.status.setText(f"결과 확인 실패: {error}")
        else:
            if self.log is not None:
                self.log.debug("POSITION", f"<< Position update verified matched={current.rect == requested} x={current.rect.x} y={current.rect.y} width={current.rect.width} height={current.rect.height}")
            self.position.set_rect(current.rect)
            self.position.status.setText("위치·크기 적용 완료" if current.rect == requested else
                                        "요청과 실제 결과가 다릅니다. 대상 앱의 크기 제한·권한을 확인하세요.")
            self.geometry_changed.emit(current)
        self.position.set_busy(False)

    def shutdown(self):
        if self.log is not None:
            self.log.debug("SETTINGS", f"- Settings windows closing")
        self.verify_timer.stop()
        self.refresh_timer.stop()
        self.pending = None
        for window in (self.window, self.position):
            window.hide()
            window.close()
