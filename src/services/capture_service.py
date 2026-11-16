"""Screen capture service for saving window screenshots to clipboard."""
import ctypes
from ctypes import wintypes

import win32con
import win32gui
import win32ui
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

from src.models.window_schema import WindowInfo

PW_RENDERFULLCONTENT = 0x00000002  # Win8.1+ : DWM/GPU 렌더링 창도 캡처


class CaptureService:
    def capture(self, target: WindowInfo) -> None:
        """Capture the specified window (without overlapping windows) to clipboard."""
        try:
            pixmap = self._grab_window(target.hwnd)
            QApplication.clipboard().setPixmap(pixmap)
        except Exception as error:
            raise OSError(f"화면 캡처 실패: {error}")

    def _grab_window(self, hwnd: int) -> QPixmap:
        # 최소화된 창은 캡처 불가 → 복원 (원하지 않으면 예외 처리로 바꾸세요)
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width, height = right - left, bottom - top
        if width <= 0 or height <= 0:
            raise ValueError("창 크기가 올바르지 않습니다.")

        hwnd_dc = win32gui.GetWindowDC(hwnd)
        src_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        mem_dc = src_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(src_dc, width, height)
        mem_dc.SelectObject(bitmap)

        try:
            ok = ctypes.windll.user32.PrintWindow(
                hwnd, mem_dc.GetSafeHdc(), PW_RENDERFULLCONTENT
            )
            if not ok:
                raise OSError("PrintWindow 호출 실패")

            bmp_info = bitmap.GetInfo()
            bmp_bits = bitmap.GetBitmapBits(True)
            image = QImage(
                bmp_bits,
                bmp_info["bmWidth"],
                bmp_info["bmHeight"],
                bmp_info["bmWidthBytes"],
                QImage.Format.Format_ARGB32,
            )
            # bits 버퍼가 해제되기 전에 deep copy
            return QPixmap.fromImage(image.copy())
        finally:
            win32gui.DeleteObject(bitmap.GetHandle())
            mem_dc.DeleteDC()
            src_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)