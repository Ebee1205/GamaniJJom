"""기본 화면 배치. 서비스 호출과 동작 처리는 MainWindow가 담당한다."""
import tkinter as tk
from tkinter import ttk
from collections.abc import Callable

from src.ui.components.cmp_buttons import RefreshButton
from src.ui.components.geometry_editor import GeometryEditor
from src.ui.components.cmp_table import CmpTable

TITLE_FONT = ("맑은 고딕", 17, "bold")
HINT_TEXT = ("화면 픽셀·창 바깥 테두리 기준 / 음수 X·Y 지원 / "
             "최소화·최대화 창은 복원 후 적용")


class MainLayout(ttk.Frame):
    def __init__(self, parent: tk.Misc, *, on_refresh: Callable[[], None],
                 on_select: Callable, on_apply: Callable[[], None]) -> None:
        super().__init__(parent, padding=16)
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(toolbar, text="실행 중인 창", font=TITLE_FONT).pack(side=tk.LEFT)
        self.refresh_button = RefreshButton(toolbar, on_refresh)
        self.refresh_button.pack(side=tk.RIGHT)
        self.table = CmpTable(self, on_select)
        self.table.pack(fill=tk.BOTH, expand=True)
        self.editor = GeometryEditor(self, on_apply)
        self.editor.pack(fill=tk.X, pady=(12, 8))
        self.status = tk.StringVar(master=self, value="창 목록을 읽는 중…")
        ttk.Label(self, text=HINT_TEXT).pack(anchor=tk.W)
        ttk.Label(self, textvariable=self.status).pack(anchor=tk.W, pady=(6, 0))
