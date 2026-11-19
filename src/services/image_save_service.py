"""Save a QPixmap as a PNG file and/or copy it to the clipboard. No window capture here."""
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from src.runtime_paths import data_root


class ImageSaveService:
    def __init__(self, save_path: str | Path = "D:/saves/"):
        self.configure(save_path)

    def configure(self, save_path: str | Path, prefix: str = "capture_",
                  postfix_date_enabled: bool = True,
                  postfix_date_format: str = "%Y%m%d_%H%M%S_%f") -> None:
        if not str(save_path).strip():
            raise ValueError("캡처 저장 경로가 비어 있습니다.")
        self.save_path = self._resolve_directory(save_path)
        self.prefix = prefix
        self.postfix_date_enabled = postfix_date_enabled
        self.postfix_date_format = postfix_date_format
        self._new_filename()  # Validate filename options before they are used by a capture.

    def save_png(self, pixmap: QPixmap) -> Path:
        """PNG로 저장하고 파일 경로를 반환한다. (인코딩을 먼저 끝내서 실패 시 빈 파일이 남지 않음)"""
        if pixmap.isNull():
            raise OSError("캡처 이미지가 비어 있습니다.")

        encoded = self._encode_png(pixmap)
        self.save_path.mkdir(parents=True, exist_ok=True)
        output_path = self.save_path / self._new_filename()
        with output_path.open("xb") as image_file:
            image_file.write(encoded)
        return output_path

    @staticmethod
    def copy_to_clipboard(pixmap: QPixmap) -> None:
        QApplication.clipboard().setPixmap(pixmap)

    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_directory(save_path: str | Path) -> Path:
        """상대 경로면 프로젝트 루트 기준으로 해석한다."""
        directory = Path(save_path).expanduser()
        if not directory.is_absolute():
            directory = data_root() / directory
        return directory

    @staticmethod
    def _encode_png(pixmap: QPixmap) -> bytes:
        buffer = QBuffer()
        if not buffer.open(QIODevice.OpenModeFlag.WriteOnly) or not pixmap.save(buffer, "PNG"):
            raise OSError("PNG 이미지 변환에 실패했습니다.")
        try:
            return bytes(buffer.data())
        finally:
            buffer.close()

    def _new_filename(self) -> str:
        date = datetime.now().strftime(self.postfix_date_format) if self.postfix_date_enabled else ""
        stem = f"{self.prefix}{date}"
        if any(char in stem for char in '<>:"/\\|?*') or any(ord(char) < 32 for char in stem):
            raise ValueError("파일명 접두어 또는 날짜 형식에 사용할 수 없는 문자가 있습니다.")
        separator = "" if not stem or stem.endswith(("_", "-")) else "_"
        return f"{stem}{separator}{uuid4().hex[:8]}.png"
