"""Connect settings window with app configuration and services."""
from PySide6.QtCore import QObject, Signal

from src.ui.settings.setting_dialog import SettingDialog


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
        self._unsaved_changes = {}  # 저장되지 않은 변경사항 추적
        
        # 로거 설정
        window.log = self.log
        
        # 시그널 연결
        window.setting_changed.connect(self._on_setting_changed)
        window.accepted.connect(self._on_accepted)
        window.rejected.connect(self._on_rejected)
        window.finished.connect(lambda result: self.closed.emit())

    def show(self) -> None:
        """Open the reusable settings popup without starting a nested event loop."""
        if self.log is not None:
            self.log.debug("SETTINGS", ">> Settings dialog requested")
        
        # 현재 설정 로드
        self.load_config()
        
        if not self.window.isVisible():
            self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def load_config(self) -> None:
        """Load current configuration from app context and display it."""
        if self.log is not None:
            self.log.debug("SETTINGS", ">> Load configuration into UI")
        
        try:
            if self.ctx.cfg is None:
                raise RuntimeError("Configuration not loaded yet.")
            
            # UI에 현재 설정값 로드
            self.window.load_config(self.ctx.cfg)
            self._unsaved_changes.clear()
            
            if self.log is not None:
                self.log.debug("SETTINGS", "<< Configuration loaded into UI")
        except Exception as e:
            if self.log is not None:
                self.log.debug("SETTINGS", f"!! Failed to load config: {e}")
            self.notification.emit(f"설정 로드 실패: {e}")

    def _on_setting_changed(self, key: str, value) -> None:
        """UI에서 설정값이 변경되었을 때 호출."""
        if self.log is not None:
            self.log.debug("SETTINGS", f">> Setting changed in UI {key} = {value}")
        
        # 변경사항을 임시로 저장
        self._unsaved_changes[key] = value

    def _on_accepted(self) -> None:
        """저장 버튼 클릭 시."""
        if self.log is not None:
            self.log.debug("SETTINGS", f">> Settings save requested ({len(self._unsaved_changes)} changes)")
        
        if not self._unsaved_changes:
            return
        
        try:
            # 모든 변경사항을 한 번에 저장
            self.update_settings(self._unsaved_changes)
            
            if self.log is not None:
                self.log.debug("SETTINGS", "<< Settings saved successfully")
            self.notification.emit("설정이 저장되었습니다.")
        except Exception as e:
            if self.log is not None:
                self.log.debug("SETTINGS", f"!! Failed to save settings: {e}")
            self.notification.emit(f"설정 저장 실패: {e}")

    def _on_rejected(self) -> None:
        """닫기/취소 버튼 클릭 시."""
        if self.log is not None:
            self.log.debug("SETTINGS", ">> Settings dialog cancelled")
        
        # 변경사항 초기화
        self._unsaved_changes.clear()

    def update_setting(self, key: str, value) -> None:
        """Update a single setting value.
        
        Args:
            key: Dot-separated config key (e.g., "logger.level", "save.scale")
            value: New value for the setting
        """
        if self.log is not None:
            self.log.debug("SETTINGS", f">> Update setting {key} = {value}")
        
        try:
            # 설정 값 변경 (메모리에만 저장)
            self.ctx.set_config_value(key, value)
            
            # 변경사항 저장 (파일에 쓰기)
            self.save()
            
            if self.log is not None:
                self.log.debug("SETTINGS", f"<< Setting updated {key}")
            self.config_changed.emit()
        except Exception as e:
            if self.log is not None:
                self.log.debug("SETTINGS", f"!! Failed to update setting {key}: {e}")
            self.notification.emit(f"설정 변경 실패: {e}")

    def update_settings(self, changes: dict) -> None:
        """Update multiple settings at once.
        
        Args:
            changes: Dictionary of key-value pairs to update
        """
        if self.log is not None:
            self.log.debug("SETTINGS", f">> Update multiple settings {len(changes)} items")
        
        try:
            # 여러 설정 값 변경 (메모리에만 저장, 검증 포함)
            self.ctx.update_config(changes)
            
            # 변경사항 저장 (파일에 쓰기)
            self.save()
            
            if self.log is not None:
                self.log.debug("SETTINGS", f"<< Settings updated")
            self.config_changed.emit()
            self._unsaved_changes.clear()
        except Exception as e:
            if self.log is not None:
                self.log.debug("SETTINGS", f"!! Failed to update settings: {e}")
            self.notification.emit(f"설정 변경 실패: {e}")

    def save(self) -> None:
        """Save current configuration changes to file.
        
        This method is automatically called by update_setting() and update_settings().
        """
        if self.log is not None:
            self.log.debug("SETTINGS", ">> Save configuration to file")
        
        try:
            self.ctx.save_config()
            if self.log is not None:
                self.log.debug("SETTINGS", "<< Configuration saved")
        except Exception as e:
            if self.log is not None:
                self.log.debug("SETTINGS", f"!! Failed to save config: {e}")
            self.notification.emit(f"설정 저장 실패: {e}")

    def dispose(self) -> None:
        """Clean up resources."""
        if self.log is not None:
            self.log.debug("SETTINGS", "-- Settings controller disposed")
        self.window.reject()
        self.deleteLater()

