"""Capture a window, save it as PNG, and copy it to the clipboard."""
from pathlib import Path

from src.adapters.windows.window_grabber import WindowGrabber
from src.models.window_schema import WindowInfo
from src.services.image_save_service import ImageSaveService


class CaptureService:
    """캡처(WindowGrabber)와 저장(ImageSaveService)을 순서대로 호출하고 로그를 남긴다."""

    def __init__(self, save_path: str | Path = "D:/saves/", log=None,
                 grabber: WindowGrabber | None = None,
                 saver: ImageSaveService | None = None):
        self.log = log
        self.grabber = grabber or WindowGrabber()
        self.saver = saver or ImageSaveService(save_path)

    @property
    def save_path(self) -> Path:
        return self.saver.save_path

    def capture(self, target: WindowInfo) -> Path:
        """Save the selected window to the configured folder; return its PNG path."""
        try:
            pixmap = self.grabber.grab(target.hwnd)
            output_path = self.saver.save_png(pixmap)
            self._debug(
                f"++ Capture saved path={ascii(str(output_path))} "
                f"{self._target_info(target)} result=saved"
            )
            self._copy_to_clipboard(pixmap)
            return output_path
        except Exception as error:
            self._debug(
                f"<< Capture failed {self._target_info(target)} "
                f"error_type={type(error).__name__} result=failed"
            )
            raise OSError(f"화면 캡처 실패: {error}") from error

    # ------------------------------------------------------------------
    def _copy_to_clipboard(self, pixmap) -> None:
        """클립보드 복사는 부가 기능이므로 실패해도 캡처 자체는 성공으로 처리한다."""
        try:
            self.saver.copy_to_clipboard(pixmap)
        except Exception as error:
            self._debug(
                f"<< Clipboard copy failed error_type={type(error).__name__} result=file_saved"
            )

    @staticmethod
    def _target_info(target: WindowInfo) -> str:
        return f"hwnd={target.handle_text} pid={target.pid}"

    def _debug(self, message: str) -> None:
        if self.log is not None:
            self.log.debug("CAPTURE", message)