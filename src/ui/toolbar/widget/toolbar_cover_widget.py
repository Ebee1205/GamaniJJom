"""The toolbar's main face. Click captures, dragging moves, right-press expands.

Behaviour is theme-independent; the active ToolbarTheme only supplies the shape
and the painting. Signals and the small action/state surface below form the
contract the controller talks to.
"""
from math import hypot
import time

from PySide6.QtCore import QEvent, QPoint, QPointF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication, QMenu, QWidget
from shiboken6 import isValid

from src.ui.cmm.cmm_button import CmmButton
from src.ui.toolbar.widget.toolbar_inner_widget import ToolbarInnerWidget
from src.ui.toolbar.widget.toolbar_theme import CoverState

DRAG_THRESHOLD = 5   # logical pixels before a press becomes a drag


class ToolbarCoverWidget(QWidget):
    # ---- Controller contract: requests ----------------------------------------------
    window_list_requested = Signal()
    disconnect_requested = Signal()
    lock_requested = Signal()
    capture_requested = Signal()
    region_capture_requested = Signal()
    position_requested = Signal()
    capture_options_requested = Signal()
    settings_requested = Signal()
    attach_requested = Signal()
    hide_requested = Signal()
    reset_requested = Signal()
    quit_requested = Signal()
    pick_requested = Signal()
    # ---- Drag session boundaries -----------------------------------------------------
    dragged = Signal(int, int)  # Compatibility only; the controller uses the boundaries below.
    drag_started = Signal()
    drag_moved = Signal()
    drag_finished = Signal()
    drag_cancelled = Signal()
    # ---- Expand / collapse -----------------------------------------------------------
    expanded_changed = Signal(bool)

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.log = None
        self.theme = theme
        self.dock = None
        self.setObjectName('toolbarCover')
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._press = None
        self._moving = False
        self._primary_screen = True
        self._busy = False
        self._flash_until = 0
        self._angle = 0
        self._more_pending = False

        self._build_actions()
        self._build_more_menu()
        self.menu = ToolbarInnerWidget(self)   # the expanded menu
        self.menu.opened.connect(lambda: self.expanded_changed.emit(True))
        self.menu.closed.connect(lambda: self.expanded_changed.emit(False))
        QApplication.instance().focusWindowChanged.connect(self._more_focus_changed)

        self._pulse = QTimer(self)
        self._pulse.setInterval(16)
        self._pulse.timeout.connect(self._animate)
        self.set_theme(theme)
        self.set_target(None)

    def _build_actions(self):
        # Hidden state/action holders: checked/enabled state and click signals the
        # controller already relies on. They are never shown.
        self.lock_button = CmmButton('unlock', '현재 위치·크기 고정', self, checkable=True)
        self.capture_button = CmmButton('capture', '화면 캡처 · 준비 중', self)
        self.lock_button.clicked.connect(lambda: self.lock_requested.emit())
        self.lock_button.secondary_requested.connect(self.position_requested.emit)
        self.capture_button.clicked.connect(self.capture_requested.emit)
        self.capture_button.secondary_requested.connect(self.capture_options_requested.emit)
        self.lock_button.toggled.connect(lambda _checked: self.update())
        self.lock_button.hide()
        self.capture_button.hide()

    def _build_more_menu(self):
        self.more_menu = QMenu(self)
        for text, signal in (('위치 초기화', self.reset_requested),
                             ('설정', self.settings_requested),
                             ('종료', self.quit_requested)):
            self.more_menu.addAction(text, signal.emit)
        self.more_menu.triggered.connect(
            lambda action: self._log(f'>> Menu action selected index={self.more_menu.actions().index(action)}'))
        self.more_menu.aboutToHide.connect(lambda: self._log('<< More menu closed'))

    def _log(self, message):
        if self.log is not None:
            self.log.debug('TOOLBAR', message)

    # ---- Theme -----------------------------------------------------------------------
    def set_theme(self, theme):
        self.collapse()
        self.theme = theme
        self.setFixedSize(theme.cover_size)
        self.update()

    def sizeHint(self):
        return self.theme.cover_size if self.theme is not None else QSize(60, 60)

    def cover_state(self):
        return CoverState(
            dock=self.dock, locked=self.lock_button.isChecked(), hovered=self.underMouse(),
            primary_screen=self._primary_screen, busy=self._busy, spin_angle=self._angle,
            flashing=time.monotonic() < self._flash_until)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.theme.paint_cover(painter, QPointF(self.width() / 2, self.height() / 2), self.cover_state())

    # ---- Expand / collapse -----------------------------------------------------------
    @property
    def is_expanded(self):
        return self.menu.isVisible()

    def _global_center(self):
        return self.mapToGlobal(QPoint(self.width() // 2, self.height() // 2))

    def expand(self, *, right_tracking=False):
        if not self.is_expanded:
            self.menu.open_ring(self._global_center(), right_tracking=right_tracking)

    def collapse(self):
        self.menu.close_menu()

    def toggle_expanded(self):
        self.menu.open_ring(self._global_center())

    show_menu = toggle_expanded   # name used before the base toolbar was removed

    # ---- Pointer: click / drag / right-press -----------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.globalPosition()
            self._moving = False
        elif event.button() == Qt.MouseButton.RightButton:
            self.expand(right_tracking=True)
        event.accept()

    def mouseMoveEvent(self, event):
        if self._press is not None:
            if not event.buttons() & Qt.MouseButton.LeftButton:
                self.cancel_drag()
                return
            delta = event.globalPosition() - self._press
            if not self._moving and hypot(delta.x(), delta.y()) >= DRAG_THRESHOLD:
                self._moving = True
                self.drag_started.emit()
            if self._moving:
                self.drag_moved.emit()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._press is not None:
            moving = self._moving
            self._press = None
            self._moving = False
            if moving:
                self.drag_finished.emit()
            elif self.theme.cover_contains(event.position()):
                self.request_capture()
        event.accept()

    def cancel_drag(self):
        moving = self._moving
        self._press = None
        self._moving = False
        if self.mouseGrabber() is self:
            self.releaseMouse()
        if moving:
            self.drag_cancelled.emit()

    @property
    def handle(self):
        """The drag surface is the cover itself (kept for callers of the old handle)."""
        return self

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def event(self, event):
        if event.type() in (QEvent.Type.UngrabMouse, QEvent.Type.Hide):
            self.cancel_drag()
        return super().event(event)

    # ---- "More" popup (reset / settings / quit) --------------------------------------
    def show_more_menu(self):
        self.menu.close_menu()
        self._more_pending = True
        # Wait for focus changes from hidden windows before creating a popup.
        QTimer.singleShot(0, self._open_more_menu)

    def _more_focus_changed(self, _window):
        if self._more_pending:
            QTimer.singleShot(0, self._open_more_menu)

    def _open_more_menu(self):
        if not self._more_pending:
            return
        if not self.isVisible() or self.menu.isVisible():
            self._more_pending = False
            return
        focus = QApplication.focusWindow()
        if focus is not None and not focus.isVisible():
            return
        self._more_pending = False
        self.more_menu.popup(self._global_center())

    # ---- Docking ---------------------------------------------------------------------
    def set_dock(self, edge):
        if edge == self.dock:
            return
        self.dock = edge
        self.update()
        window = self.window()
        if window is not self and hasattr(window, 'apply_shape'):
            window.apply_shape()
        self.menu.update()

    # ---- Tools (called by the inner menu) --------------------------------------------
    def request_capture(self):
        if self._busy:
            return
        self.capture_button.click()

    def activate_tool(self, tool_id):
        if tool_id == 'app_select':
            self.pick_requested.emit()
        elif tool_id == 'window_list':
            self.window_list_requested.emit()
        elif tool_id == 'disconnect' and self.tool_enabled(tool_id):
            self.disconnect_requested.emit()
        elif tool_id == 'lock':
            self.lock_button.click()
        elif tool_id == 'more':
            self.show_more_menu()
        elif tool_id == 'reset':
            self.reset_requested.emit()
        elif tool_id == 'settings':
            self.settings_requested.emit()
        elif tool_id == 'window_size':
            self.position_requested.emit()
        elif tool_id == 'region_capture':
            self.region_capture_requested.emit()

    def tool_enabled(self, tool_id):
        if tool_id == 'disconnect':
            return not self._primary_screen
        if tool_id in ('lock', 'window_size'):
            return self.lock_button.isEnabled()
        return True

    def tool_checked(self, tool_id):
        return self.lock_button.isChecked() if tool_id == 'lock' else False

    # ---- State pushed by the controller ----------------------------------------------
    def set_target(self, target):
        self._primary_screen = target is None
        self.lock_button.setEnabled(target is not None)
        text = '주모니터 전체 화면 캡처' if target is None else f'{target.title} · 클릭: 캡처'
        self.setAccessibleName(text)
        self.setToolTip(text + '\n드래그: 이동 · 우클릭: 도구')
        self.update()

    def set_locked(self, enabled: bool):
        self.lock_button.setChecked(enabled)
        self.lock_button.set_icon('lock' if enabled else 'unlock')
        text = '위치·크기 고정 중 · 클릭하여 해제' if enabled else '현재 위치·크기 고정'
        self.lock_button.setToolTip(text + ' · 우클릭: 좌표 설정')
        self.lock_button.setAccessibleName(text)
        self.update()

    def set_capture_busy(self, busy):
        self._busy = busy
        self.capture_button.setEnabled(not busy)
        if not busy:
            self._flash_until = time.monotonic() + .16
        self._pulse.start()
        self.update()

    def _animate(self):
        self._angle = (self._angle + 12) % 360
        self.update()
        if self.menu.isVisible():
            self.menu.update()
        if not self._busy and time.monotonic() >= self._flash_until:
            self._pulse.stop()

    # ---- Lifecycle -------------------------------------------------------------------
    def hideEvent(self, event):
        self._more_pending = False
        if isValid(self.menu):   # already gone while the application shuts down
            self.menu.hide()
        self.more_menu.hide()
        self.cancel_drag()
        super().hideEvent(event)

    def dispose(self):
        self._more_pending = False
        self._pulse.stop()
        try:
            QApplication.instance().focusWindowChanged.disconnect(self._more_focus_changed)
        except (RuntimeError, TypeError):
            pass
        self.more_menu.hide()
        self.menu.close_menu()
        self.menu.deleteLater()
