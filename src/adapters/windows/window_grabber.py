"""Grab a window's pixels as a QPixmap (Win32 PrintWindow)."""
import ctypes

import win32con
import win32gui
import win32ui
from PySide6.QtGui import QImage, QPixmap

PW_RENDERFULLCONTENT = 0x00000002  # Win8.1+ : DWM/GPU 렌더링 창도 캡처


class WindowGrabber:
    """창 핸들(hwnd)을 받아 화면 이미지를 QPixmap으로 반환한다."""

    def grab(self, hwnd: int) -> QPixmap:
        self._restore_if_minimized(hwnd)
        width, height = self._window_size(hwnd)
        return self._print_window(hwnd, width, height)

    # ------------------------------------------------------------------
    @staticmethod
    def _restore_if_minimized(hwnd: int) -> None:
        # 최소화된 창은 캡처 불가 → 복원 (원하지 않으면 예외 처리로 바꾸세요)
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

    @staticmethod
    def _window_size(hwnd: int) -> tuple[int, int]:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width, height = right - left, bottom - top
        if width <= 0 or height <= 0:
            raise ValueError("창 크기가 올바르지 않습니다.")
        return width, height

    @staticmethod
    def _print_window(hwnd: int, width: int, height: int) -> QPixmap:
        """창을 메모리 DC에 그린 뒤 QPixmap으로 변환한다. GDI 리소스는 항상 해제한다."""
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        src_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        mem_dc = None
        bitmap = None
        try:
            mem_dc = src_dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(src_dc, width, height)
            mem_dc.SelectObject(bitmap)

            ok = ctypes.windll.user32.PrintWindow(
                hwnd, mem_dc.GetSafeHdc(), PW_RENDERFULLCONTENT
            )
            if not ok:
                raise OSError("PrintWindow 호출 실패")

            return WindowGrabber._bitmap_to_pixmap(bitmap)
        finally:
            if bitmap is not None:
                win32gui.DeleteObject(bitmap.GetHandle())
            if mem_dc is not None:
                mem_dc.DeleteDC()
            src_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)

    @staticmethod
    def _bitmap_to_pixmap(bitmap) -> QPixmap:
        info = bitmap.GetInfo()
        image = QImage(
            bitmap.GetBitmapBits(True),
            info["bmWidth"],
            info["bmHeight"],
            info["bmWidthBytes"],
            QImage.Format.Format_ARGB32,
        )
        # bits 버퍼가 해제되기 전에 deep copy
        return QPixmap.fromImage(image.copy())