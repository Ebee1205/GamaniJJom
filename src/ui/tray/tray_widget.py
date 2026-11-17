"""Tray icon and menus. Commands are exposed as signals."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from src.ui.resources import icon


class TrayWidget(QSystemTrayIcon):
    attach_requested = Signal()
    toolbar_requested = Signal()
    programs_requested = Signal()
    settings_requested = Signal()
    connection_requested = Signal(object)
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(icon("unlock"), parent)
        self.log = parent.ctx.log if parent is not None else None
        self.setToolTip("GamaniJJom — 창 컨트롤러")
        self.menu = QMenu()
        self.menu.addAction("툴바 다시 표시", self.toolbar_requested.emit)
        self.menu.aboutToShow.connect(lambda: self.log.debug("TRAY", ">> Tray menu opened") if self.log is not None else None)
        self.menu.triggered.connect(lambda action: self.log.debug("TRAY", ">> Tray menu action selected") if self.log is not None else None)
        self.menu.addAction("프로그램 목록 열기", self.programs_requested.emit)
        self.menu.addAction("설정…", self.settings_requested.emit)
        self.connections = self.menu.addMenu("연결된 프로그램")
        self.menu.addSeparator()
        self.menu.addAction("종료", self.quit_requested.emit)
        self.setContextMenu(self.menu)
        self.activated.connect(self.on_activated)

    def on_activated(self, reason):
        if self.log is not None:
            self.log.debug("TRAY", f">> Tray activated reason={reason.name}")
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.programs_requested.emit()

    def set_connections(self, attachments):
        self.connections.clear()
        for attachment in attachments:
            label = attachment.target.title.replace("&", "&&")
            label += " [Lock]" if attachment.locked_rect is not None else ""
            key = attachment.target.identity
            self.connections.addAction(label, lambda checked=False, k=key: self.connection_requested.emit(k))
        if self.connections.isEmpty():
            self.connections.addAction("연결된 창 없음").setEnabled(False)
