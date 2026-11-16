"""선택한 창의 안내 문구와 위치·크기 입력 폼."""
import tkinter as tk
from tkinter import ttk
from collections.abc import Callable

from src.models.window_schema import WindowInfo, WindowRect
from src.ui.components.cmp_buttons import ApplyButton

PLACEHOLDER_TEXT = "목록에서 창을 선택하세요."
RECT_FIELDS = (("x", "X"), ("y", "Y"), ("width", "너비"), ("height", "높이"))


class GeometryEditor(ttk.LabelFrame):
    def __init__(self, parent: tk.Misc, on_apply: Callable[[], None]) -> None:
        super().__init__(parent, text="선택한 창의 위치·크기", padding=12)
        self.target_text = tk.StringVar(master=self, value=PLACEHOLDER_TEXT)
        self.inputs: dict[str, tk.StringVar] = {}
        ttk.Label(self, textvariable=self.target_text, wraplength=750).grid(
            row=0, column=0, columnspan=9, sticky="w", pady=(0, 8))
        for index, (key, label) in enumerate(RECT_FIELDS):
            ttk.Label(self, text=label).grid(row=1, column=index * 2, padx=(0, 5))
            variable = tk.StringVar(master=self)
            self.inputs[key] = variable
            ttk.Entry(self, textvariable=variable, width=11).grid(
                row=1, column=index * 2 + 1, padx=(0, 12))
        self.apply_button = ApplyButton(self, on_apply)
        self.apply_button.grid(row=1, column=8)

    def clear(self) -> None:
        self.apply_button.configure(state=tk.DISABLED)
        self.target_text.set(PLACEHOLDER_TEXT)
        for variable in self.inputs.values():
            variable.set("")

    def show_target(self, info: WindowInfo) -> None:
        self.target_text.set(f"{info.title}  |  HWND {info.handle_text}  |  PID {info.pid}")
        for key, variable in self.inputs.items():
            variable.set(str(getattr(info.rect, key)))
        self.apply_button.configure(state=tk.NORMAL)

    def read_rect(self) -> WindowRect:
        try:
            values = [int(self.inputs[key].get()) for key, _ in RECT_FIELDS]
        except ValueError:
            raise ValueError("X/Y/너비/높이는 정수로 입력하세요.") from None
        return WindowRect(*values)
