"""Tray lifetime and menus; all actions are supplied by the coordinator."""
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon


class Tray(QSystemTrayIcon):
    def __init__(self, owner):
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)
        super().__init__(icon, owner)
        self.setToolTip("GamaniJJom — 창 컨트롤러")
        self.menu = QMenu()
        self.menu.addAction("프로그램 연결…", owner.show_picker)
        self.menu.addAction("화면에서 창 선택…", owner.start_pick)
        self.menu.addAction("모든 툴바 다시 표시", owner.reveal)
        self.connections = self.menu.addMenu("연결된 프로그램")
        self.connections.aboutToShow.connect(lambda: self.refresh_connections(owner))
        self.menu.addSeparator()
        self.menu.addAction("종료", QApplication.instance().quit)
        self.setContextMenu(self.menu)
        self.activated.connect(
            lambda reason: owner.show_picker()
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None
        )

    def refresh_connections(self, owner):
        self.connections.clear()
        for identity, attachment in owner.attachments.attachments.items():
            label = attachment.target.title.replace("&", "&&")
            label += " [Lock]" if attachment.locked_rect else ""
            self.connections.addAction(label, lambda checked=False, key=identity: owner.show_connection(key))
        if self.connections.isEmpty():
            self.connections.addAction("연결된 창 없음").setEnabled(False)
