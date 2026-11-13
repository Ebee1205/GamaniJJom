"""창 관리 동작을 연결하는 컨트롤러. 화면 구성은 components에 위임한다."""
import tkinter as tk
from tkinter import messagebox

from src.models.window_schema import WindowInfo, WindowRect
from src.services.window_service import WindowService
from src.ui.components.main_layout import MainLayout

VERIFY_DELAY_MS = 300


class MainWindow(tk.Tk):
    def __init__(self, service: WindowService | None = None) -> None:
        super().__init__()
        self.service = service or WindowService()
        self.windows: dict[str, WindowInfo] = {}
        self.selected: WindowInfo | None = None
        self.title("GamaniJJom — 창 위치·크기")
        self.geometry("1050x600")
        self.minsize(820, 450)

        self.layout = MainLayout(self, on_refresh=self.refresh,
                                 on_select=self.on_select, on_apply=self.apply)
        self.layout.pack(fill=tk.BOTH, expand=True)
        self.table = self.layout.table
        self.editor = self.layout.editor
        self.status = self.layout.status
        # 기존 호출부와 테스트에서 사용하는 위젯 참조를 유지한다.
        self.tree = self.table.tree
        self.inputs = self.editor.inputs
        self.target_text = self.editor.target_text
        self.apply_button = self.editor.apply_button
        self.refresh_button = self.layout.refresh_button

        self.bind("<F5>", lambda _: self.refresh())
        self.after_idle(self.refresh)

    def _is_selected(self, info: WindowInfo) -> bool:
        return self.selected is not None and self.selected.identity == info.identity

    def _update_row(self, info: WindowInfo) -> None:
        if self.table.update_window(info):
            self.windows[str(info.hwnd)] = info

    def _reload_rows(self, windows: list[WindowInfo]) -> None:
        self.windows = {str(info.hwnd): info for info in windows}
        self.table.replace(windows)

    def _clear_selection(self) -> None:
        self.selected = None
        self.editor.clear()

    def _show_target(self, info: WindowInfo) -> None:
        self.selected = info
        self.editor.show_target(info)

    def _restore_selection(self, previous: WindowInfo | None) -> None:
        if previous is None:
            return
        current = self.windows.get(str(previous.hwnd))
        if current is None or current.identity != previous.identity:
            return
        self.table.select(current.hwnd)
        self._show_target(current)

    def _read_rect_inputs(self) -> WindowRect:
        return self.editor.read_rect()

    # --------------------------------------------------------------- handlers
    def refresh(self) -> None:
        previous = self.selected
        self._clear_selection()
        try:
            windows = self.service.list_windows()
        except OSError as error:
            self.status.set(f"목록 조회 실패: {error}")
            return
        self._reload_rows(windows)
        self._restore_selection(previous)
        self.status.set(f"창 {len(windows)}개 / 숨김·도구 창과 이 프로그램은 제외")

    def on_select(self, _event=None) -> None:
        item = self.table.selected_item()
        if item is None:
            self._clear_selection()
            return
        target = self.windows.get(item)
        if target is None:
            return
        try:
            current = self.service.read(target)
        except OSError as error:
            self._clear_selection()
            self.status.set(str(error))
            return
        self._update_row(current)
        self._show_target(current)

    def apply(self) -> None:
        target = self.selected
        if target is None:
            return
        try:
            rect = self._read_rect_inputs()
            self.service.apply(target, rect)
        except (ValueError, OSError) as error:
            self.status.set(f"적용 실패: {error}")
            messagebox.showwarning("위치·크기 적용", str(error), parent=self)
            return
        self.status.set("변경 요청을 보냈습니다. 실제 위치·크기를 확인하는 중…")
        self.apply_button.configure(state=tk.DISABLED)
        self.after(VERIFY_DELAY_MS, lambda: self._verify_apply(target, rect))

    def _verify_apply(self, target: WindowInfo, requested: WindowRect) -> None:
        try:
            current = self.service.read(target)
        except OSError as error:
            if self._is_selected(target):
                self._clear_selection()
            self.status.set(f"적용 결과 확인 실패: {error}")
            return

        self._update_row(current)
        if self._is_selected(target):
            self._show_target(current)

        if current.rect == requested:
            self.status.set("위치·크기 적용 완료")
        else:
            self.status.set("요청과 실제 위치·크기가 다릅니다. "
                            "대상 앱의 크기 제한이나 응답 지연을 확인하세요.")