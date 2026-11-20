"""
Copyright (c) 2025. Ebee1205(wavicle) all rights reserved.

The copyright of this software belongs to Ebee1205(wavicle).
All rights reserved.
"""

import logging
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from src.modules import logger
from src.modules.config_handler import ConfigHandler


class LoggerConfig(BaseModel):
    level: str
    path: str
    suffix: str
    max_bytes: int
    max_files: str
    rotation: str
    use_console: bool


class FilenameConfig(BaseModel):
    prefix: str = "capture_"
    postfix_date_enabled: bool = True
    postfix_date_format: str = "%Y%m%d_%H%M%S_%f"


class SaveConfig(BaseModel):
    path: str
    scale: Literal[1, 2, 3] = 1
    notification_enabled: bool = True
    copy_to_clipboard: bool = True
    filename: FilenameConfig = Field(default_factory=FilenameConfig)

class DevModeConfig(BaseModel):
    devMode: bool = False


ToolbarThemeName = Literal["circle", "square"]


class AppConfig(BaseModel):
    environment: str
    project_name: str
    logger: LoggerConfig
    save: SaveConfig
    theme: ToolbarThemeName = "square"
    devMode: bool = False

    @field_validator("devMode", mode="before")
    @classmethod
    def read_dev_mode(cls, value):
        if isinstance(value, (dict, DevModeConfig)):
            return DevModeConfig.model_validate(value).devMode
        return value


class AppContext:
    def __init__(self):
        self.cfg: Optional[AppConfig] = None
        self.cfg_handler: Optional[ConfigHandler[AppConfig]] = None
        self.log = None

    def load_config(self, path: str) -> AppConfig:
        """Load and validate configuration from JSON file."""
        print("+ start load cfg")
        
        handler = ConfigHandler(path, AppConfig)
        self.cfg = handler.load()          # 실패하면 예외처리
        self.cfg_handler = handler
            
        print("- end load cfg")
        return self.cfg

    def get_config_value(self, key: str, default=None):
        """Get a configuration value by dot-separated path. Example: get_config_value("logger.level")"""
        if self.cfg_handler is None:
            raise RuntimeError("Configuration not loaded yet. Call load_config() first.")
        return self.cfg_handler.get(key, default)

    def set_config_value(self, key: str, value) -> AppConfig:
        """Set a configuration value. Changes are in-memory only until save_config() is called."""
        if self.cfg_handler is None:
            raise RuntimeError("Configuration not loaded yet. Call load_config() first.")
        if self.log is not None:
            self.log.info(f"+ set cfg {key} = {value}")
        self.cfg = self.cfg_handler.set(key, value)
        return self.cfg

    def update_config(self, changes: dict) -> AppConfig:
        """Update multiple configuration values at once."""
        if self.log is not None:
            self.log.info("+ update cfg")
        if self.cfg_handler is None:
            raise RuntimeError("Configuration not loaded yet. Call load_config() first.")
        self.cfg = self.cfg_handler.update(changes)
        return self.cfg

    def save_config(self) -> None:
        """Save current configuration to file."""
        if self.log is not None:
            self.log.info("+ save cfg")
        if self.cfg_handler is None:
            raise RuntimeError("Configuration not loaded yet. Call load_config() first.")
        self.cfg_handler.save()

    def load_json_map(self, name: str, path: str) -> bool:
        """Load arbitrary JSON file and register it dynamically on context."""
        try:
            import orjson
            with open(path, "rb") as f:
                data = orjson.loads(f.read().lstrip(b"\xef\xbb\xbf"))
            setattr(self, name, data)
            print(f"> loaded JSON map '{name}' from {path}")
            return True
        except Exception as e:
            print(f"!! failed to load JSON map '{name}' from {path}: {e}")
            return False

    def _init_logger(self):
        """Initialize application logger from configuration."""
        print("+ start init logger")

        if self.cfg is None:
            raise RuntimeError("Configuration must be loaded before initializing the logger.")

        log_level = self.cfg.logger.level
        log_path = self.cfg.logger.path
        log_max_files = self.cfg.logger.max_files
        self.log = logger.setup_logger(log_level, log_path, log_max_files)

        self.log.debug("- end init logger")

    def shutdown(self):
        """Cleanup on application exit."""
        if self.log is not None:
            self.log.info("APP", "Application stopped")
        logging.shutdown()
