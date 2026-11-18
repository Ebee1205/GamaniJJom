"""Non-activating, click-through preview; never changes the target window."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget

from src.ui.resources import theme_color


class WindowHighlightOverlay(QWidget):
    def __init__(self):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                 | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus
                 | Qt.WindowType.WindowTransparentForInput | Qt.WindowType.NoDropShadowWindowHint)
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAutoFillBackground(False)
        self.setWindowTitle("GamaniJJom window preview")
        self.resize(1, 1)  # Native placement supplies size; avoid a default-size flash.
        self.selection = False

    def set_selection(self, enabled):
        if self.selection != enabled:
            self.selection = enabled
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        if rect.isEmpty():
            return
        if self.selection:
            # Low opacity keeps the hovered application's content readable.
            painter.setBrush(theme_color('bg-window-selection'))
            painter.setPen(QPen(theme_color('border-window-selection'), 3))
            painter.drawRoundedRect(rect, 5, 5)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(theme_color('border-window-selection-glow'), 6))
            painter.drawRoundedRect(rect.adjusted(3, 3, -3, -3), 4, 4)
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(theme_color('border-window-snap'), 3))
            painter.drawRect(rect)
