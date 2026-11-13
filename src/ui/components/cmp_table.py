"""창 목록의 열, 스크롤, 행 표시와 선택을 담당한다."""
import tkinter as tk
from tkinter import ttk
from collections.abc import Callable

from src.models.window_schema import WindowInfo

COLUMNS = (
    ("hwnd", "HWND", 110), ("pid", "PID", 75), ("title", "제목", 350),
    ("x", "X", 75), ("y", "Y", 75), ("width", "너비", 75), ("height", "높이", 75),
)


class CmpTable(ttk.Frame):
    def __init__(self, parent: tk.Misc, on_select: Callable) -> None:
        super().__init__(parent)
        self.tree = ttk.Treeview(self, columns=[key for key, _, _ in COLUMNS],
                                 show="headings", selectmode="browse")
        for column, label, width in COLUMNS:
            is_title = column == "title"
            self.tree.heading(column, text=label)
            self.tree.column(column, width=width, minwidth=55, stretch=is_title,
                             anchor=tk.W if is_title else tk.E)
        yscroll = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        xscroll = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", on_select)

    @staticmethod
    def row_values(info: WindowInfo) -> tuple:
        rect = info.rect
        return (info.handle_text, info.pid, info.title,
                rect.x, rect.y, rect.width, rect.height)

    def replace(self, windows: list[WindowInfo]) -> None:
        children = self.tree.get_children()
        if children:
            self.tree.delete(*children)
        for info in windows:
            self.tree.insert("", tk.END, iid=str(info.hwnd), values=self.row_values(info))

    def update_window(self, info: WindowInfo) -> bool:
        item = str(info.hwnd)
        if not self.tree.exists(item):
            return False
        self.tree.item(item, values=self.row_values(info))
        return True

    def select(self, hwnd: int) -> None:
        item = str(hwnd)
        self.tree.selection_set(item)
        self.tree.focus(item)
        self.tree.see(item)

    def selected_item(self) -> str | None:
        selection = self.tree.selection()
        return selection[0] if selection else None
