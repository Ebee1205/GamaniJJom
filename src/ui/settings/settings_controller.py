"""Persist settings and notify runtime services only after a successful save."""
from PySide6.QtCore import QObject, Signal

from src.services.image_save_service import ImageSaveService
from src.ui.settings.setting_dialog import SettingDialog


class SettingsController(QObject):
    config_changed = Signal()
    notification = Signal(str)
    closed = Signal()

    def __init__(self, window: SettingDialog, app_context, parent=None):
        super().__init__(parent)
        self.ctx = app_context
        self.log = app_context.log
        self.window = window
        window.log = self.log
        window.settings_applied.connect(self._on_applied)
        window.rejected.connect(lambda: self._debug(">> Settings dialog cancelled"))
        window.finished.connect(lambda result: self.closed.emit())

    def show(self) -> None:
        self._debug(">> Settings dialog requested")
        if not self.window.isVisible():
            self.load_config()
            self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def load_config(self) -> None:
        try:
            if self.ctx.cfg is None:
                raise RuntimeError("Configuration not loaded yet")
            self.window.load_config(self.ctx.cfg)
            self._debug("<< Configuration loaded into UI")
        except Exception as error:
            self._debug(f"<< Configuration load failed error_type={type(error).__name__}")
            self.notification.emit(f"설정 로드 실패: {error}")

    def _on_applied(self, changes: dict) -> None:
        if self.update_settings(changes):
            self.window.mark_applied(changes)
            self.notification.emit("설정이 저장되고 적용되었습니다.")

    def update_setting(self, key: str, value) -> bool:
        return self.update_settings({key: value})

    def update_settings(self, changes: dict) -> bool:
        if not changes:
            return True
        if any(key == "logger" or key.startswith("logger.") for key in changes):
            self._debug("<< Logger settings change rejected result=startup_only")
            self.notification.emit("로그 설정은 설정 파일 수정 후 앱을 다시 시작하면 적용됩니다.")
            return False
        self._debug(f">> Settings save requested count={len(changes)}")
        previous = {key: self.ctx.get_config_value(key) for key in changes}
        updated = False
        try:
            self.ctx.update_config(changes)
            updated = True
            self._validate_config()
            self.ctx.save_config()
        except Exception as error:
            if updated:
                self.ctx.update_config(previous)
            self._debug(f"<< Settings save failed error_type={type(error).__name__} result=unchanged")
            self.notification.emit(f"설정 저장 실패: {error}")
            return False
        self._debug(f"!! Settings saved count={len(changes)} result=saved")
        self.config_changed.emit()
        return True

    def _validate_config(self) -> None:
        """Reject invalid runtime options before replacing the persisted file."""
        config = self.ctx.cfg
        saver = ImageSaveService(config.save.path)
        saver.configure(config.save.path, config.save.filename.prefix,
                        config.save.filename.postfix_date_enabled,
                        config.save.filename.postfix_date_format)

    def save(self) -> bool:
        try:
            self.ctx.save_config()
        except Exception as error:
            self._debug(f"<< Settings save failed error_type={type(error).__name__}")
            self.notification.emit(f"설정 저장 실패: {error}")
            return False
        self.config_changed.emit()
        return True

    def dispose(self) -> None:
        self._debug("- Settings controller disposed")
        self.window.reject()
        self.deleteLater()

    def _debug(self, message: str) -> None:
        if self.log is not None:
            self.log.debug("SETTINGS", message)
