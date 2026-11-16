"""Connect settings window with app configuration and services."""
from PySide6.QtCore import QObject, Signal

from ui.settings.setting_dialog import SettingDialog


class SettingsController(QObject):
    """Handles configuration changes from the settings UI.
    
    Responsibilities:
    - Load current configuration and display it in the settings window
    - Handle configuration changes from user input
    - Save configuration changes to file
    - Sync configuration state with services
    """
    
    config_changed = Signal()      # 설정이 변경되었음
    notification = Signal(str)     # 사용자에게 알림 메시지
    closed = Signal()              # 설정 창이 닫혔음

    def __init__(self, window: SettingDialog, app_context, parent=None):
        super().__init__(parent)
        self.log = parent.ctx.log if parent is not None else None
        self.window = window
        self.ctx = app_context
        
        # 로거 설정
        window.log = self.log
        
        # 시그널 연결
        window.finished.connect(lambda result: self.closed.emit())

    def show(self) -> None:
        """Open the reusable settings popup without starting a nested event loop."""
        if self.log is not None:
            self.log.debug("SETTINGS", ">> Settings dialog requested")
        if not self.window.isVisible():
            self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def load_config(self) -> None:
        """Load current configuration from app context and display it."""
        if self.log is not None:
            self.log.debug("SETTINGS_CTR", ">> Load configuration")
        
        try:
            # 현재 설정을 UI에 표시하는 로직은 여기에 추가
            # 예: self.window.display_config(self.ctx.cfg)
            if self.log is not None:
                self.log.debug("SETTINGS_CTR", "<< Configuration loaded")
        except Exception as e:
            if self.log is not None:
                self.log.debug("SETTINGS_CTR", f"!! Failed to load config: {e}")
            self.notification.emit(f"설정 로드 실패: {e}")

    def update_setting(self, key: str, value) -> None:
        """Update a single setting value.
        
        Args:
            key: Dot-separated config key (e.g., "logger.level", "save.scale")
            value: New value for the setting
        """
        if self.log is not None:
            self.log.debug("SETTINGS_CTR", f">> Update setting {key} = {value}")
        
        try:
            # 설정 값 변경 (메모리에만 저장)
            self.ctx.set_config_value(key, value)
            
            # 변경사항 저장 (파일에 쓰기)
            self.save()
            
            if self.log is not None:
                self.log.debug("SETTINGS_CTR", f"<< Setting updated {key}")
            self.config_changed.emit()
        except Exception as e:
            if self.log is not None:
                self.log.debug("SETTINGS_CTR", f"!! Failed to update setting {key}: {e}")
            self.notification.emit(f"설정 변경 실패: {e}")

    def update_settings(self, changes: dict) -> None:
        """Update multiple settings at once.
        
        Args:
            changes: Dictionary of key-value pairs to update
        """
        if self.log is not None:
            self.log.debug("SETTINGS_CTR", f">> Update multiple settings {len(changes)} items")
        
        try:
            # 여러 설정 값 변경 (메모리에만 저장, 검증 포함)
            self.ctx.update_config(changes)
            
            # 변경사항 저장 (파일에 쓰기)
            self.save()
            
            if self.log is not None:
                self.log.debug("SETTINGS_CTR", f"<< Settings updated")
            self.config_changed.emit()
        except Exception as e:
            if self.log is not None:
                self.log.debug("SETTINGS_CTR", f"!! Failed to update settings: {e}")
            self.notification.emit(f"설정 변경 실패: {e}")

    def save(self) -> None:
        """Save current configuration changes to file.
        
        This method is automatically called by update_setting() and update_settings().
        """
        if self.log is not None:
            self.log.debug("SETTINGS_CTR", ">> Save configuration to file")
        
        try:
            self.ctx.save_config()
            if self.log is not None:
                self.log.debug("SETTINGS_CTR", "<< Configuration saved")
        except Exception as e:
            if self.log is not None:
                self.log.debug("SETTINGS_CTR", f"!! Failed to save config: {e}")
            self.notification.emit(f"설정 저장 실패: {e}")

    def dispose(self) -> None:
        """Clean up resources."""
        if self.log is not None:
            self.log.debug("SETTINGS_CTR", "-- Settings controller disposed")
        self.window.reject()
        self.deleteLater()
