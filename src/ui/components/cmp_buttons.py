"""창 관리 화면에서 사용하는 동작 버튼."""
import tkinter as tk
from tkinter import ttk
from collections.abc import Callable


class RefreshButton(ttk.Button):
    def __init__(self, parent: tk.Misc, command: Callable[[], None]) -> None:
        super().__init__(parent, text="목록 새로고침 (F5)", command=command)


class ApplyButton(ttk.Button):
    def __init__(self, parent: tk.Misc, command: Callable[[], None]) -> None:
        super().__init__(parent, text="위치·크기 적용", command=command, state=tk.DISABLED)
