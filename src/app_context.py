"""
Copyright (c) 2025. Ebee1205(wavicle) all rights reserved.

The copyright of this software belongs to Ebee1205(wavicle).
All rights reserved.
"""

# app_context.py
import logging
import orjson

from pydantic import BaseModel
from typing import Any
from typing import Optional

from src.modules import logger

class LoggerConfig(BaseModel):
    level: str
    path: str
    suffix: str
    max_bytes: int
    max_files: str
    rotation: str
    use_console: bool

class AppConfig(BaseModel):
    # 상위 항목 직접 정의
    environment: str
    project_name: str
    save_path: str
    
    # 구성 요소들
    logger: LoggerConfig

class AppContext:
    def __init__(self):
        self.cfg: Optional[AppConfig] = None
        self.log = None

    def load_config(self, path: str) -> AppConfig:
        """JSON 파일을 로드하고 AppConfig 모델로 파싱"""
        print("+ start load cfg")

        with open(path, "rb") as f:
            # 윈도우 메모장이 붙이는 UTF-8 BOM 제거 (orjson은 BOM 불가)
            raw = orjson.loads(f.read().lstrip(b"\xef\xbb\xbf"))

        print("- end load cfg")
        self.cfg = AppConfig(**raw)
        return self.cfg

    def load_json_map(self, name: str, path: str):
        """
        임의의 JSON 파일을 로드하여 ctx에 동적으로 등록
        예: ctx.load_json_map("event_map", "config/event_map.json")
        → self.event_map 로 저장됨
        """
        try:
            with open(path, "rb") as f:
                data = orjson.loads(f.read().lstrip(b"\xef\xbb\xbf"))

            setattr(self, name, data)
            print(f"> loaded JSON map '{name}' from {path}")
            return True

        except Exception as e:
            print(f"!! failed to load JSON map '{name}' from {path}: {e}")
            return False

    def _init_logger(self):
        print("+ start init logger")

        if self.cfg is None:
            raise RuntimeError("Configuration must be loaded before initializing the logger.")

        log_level = self.cfg.logger.level
        log_path = self.cfg.logger.path
        log_max_files = self.cfg.logger.max_files
        self.log = logger.setup_logger(log_level, log_path, log_max_files)

        self.log.debug("- end init logger")

    def shutdown(self):
        """종료 정리"""
        if self.log is not None:
            self.log.info("APP", "Application stopped")

        logging.shutdown()
