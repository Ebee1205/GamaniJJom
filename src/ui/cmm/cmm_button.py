"""Common icon button; emits intent without knowing any application service."""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QToolButton

from src.ui.resources import icon


class CmmButton(QToolButton):
    secondary_requested = Signal()

    def __init__(self, name: str, label: str, parent=None, *, checkable=False):
        super().__init__(parent)
        self.log = None
        self.setObjectName("toolbarButton")
        self.clicked.connect(lambda checked=False: self.log.debug("TOOLBAR", f">> Button clicked action={name} checked={checked}") if self.log is not None else None)
        self.secondary_requested.connect(lambda: self.log.debug("TOOLBAR", f">> Button context requested action={name}") if self.log is not None else None)
        self.setAccessibleName(label)
        self.setToolTip(label)
        self.setIcon(icon(name))
        self.setIconSize(QSize(18, 18))
        self.setFixedSize(34, 34)
        self.setCheckable(checkable)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda _: self.secondary_requested.emit())

    def set_icon(self, name: str):
        self.setIcon(icon(name))
