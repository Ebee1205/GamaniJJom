"""Tk UI for discovering, selecting and positioning Windows application windows."""
import tkinter as tk
from tkinter import messagebox, ttk

from src.models.window_schema import WindowInfo, WindowRect
from src.services.window_service import WindowService


class MainWindow(tk.Tk):
    def __init__(self, service: WindowService | None = None) -> None:
        super().__init__()
        self.service = service or WindowService()
        self.windows: dict[str, WindowInfo] = {}
        self.selected: WindowInfo | None = None
        self.title("GamaniJJom — 창 위치·크기")
        self.geometry("1050x600")
        self.minsize(820, 450)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(toolbar, text="실행 중인 창", font=("맑은 고딕", 17, "bold")).pack(side=tk.LEFT)
        self.refresh_button = ttk.Button(toolbar, text="목록 새로고침 (F5)", command=self.refresh)
        self.refresh_button.pack(side=tk.RIGHT)

        table = ttk.Frame(frame)
        table.pack(fill=tk.BOTH, expand=True)
        columns = ("hwnd", "pid", "title", "x", "y", "width", "height")
        self.tree = ttk.Treeview(table, columns=columns, show="headings", selectmode="browse")
        for column, label, width in zip(columns,
                                       ("HWND", "PID", "제목", "X", "Y", "너비", "높이"),
                                       (110, 75, 350, 75, 75, 75, 75)):
            self.tree.heading(column, text=label)
            self.tree.column(column, width=width, minwidth=55,
                             stretch=column == "title", anchor=tk.W if column == "title" else tk.E)
        yscroll = ttk.Scrollbar(table, orient=tk.VERTICAL, command=self.tree.yview)
        xscroll = ttk.Scrollbar(table, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        editor = ttk.LabelFrame(frame, text="선택한 창의 위치·크기", padding=12)
        editor.pack(fill=tk.X, pady=(12, 8))
        self.target_text = tk.StringVar(value="목록에서 창을 선택하세요.")
        ttk.Label(editor, textvariable=self.target_text, wraplength=750).grid(
            row=0, column=0, columnspan=9, sticky="w", pady=(0, 8))
        self.inputs = {}
        for index, (key, label) in enumerate((("x", "X"), ("y", "Y"),
                                             ("width", "너비"), ("height", "높이"))):
            ttk.Label(editor, text=label).grid(row=1, column=index * 2, padx=(0, 5))
            variable = tk.StringVar()
            self.inputs[key] = variable
            ttk.Entry(editor, textvariable=variable, width=11).grid(
                row=1, column=index * 2 + 1, padx=(0, 12))
        self.apply_button = ttk.Button(editor, text="위치·크기 적용", command=self.apply,
                                       state=tk.DISABLED)
        self.apply_button.grid(row=1, column=8)
        ttk.Label(frame, text="화면 픽셀·창 바깥 테두리 기준 / 음수 X·Y 지원 / "
                             "최소화·최대화 창은 복원 후 적용").pack(anchor=tk.W)
        self.status = tk.StringVar(value="창 목록을 읽는 중…")
        ttk.Label(frame, textvariable=self.status).pack(anchor=tk.W, pady=(6, 0))
        self.bind("<F5>", lambda _: self.refresh())
        self.after_idle(self.refresh)

    @staticmethod
    def _values(info: WindowInfo) -> tuple:
        return (f"0x{info.hwnd:X}", info.pid, info.title, info.rect.x, info.rect.y,
                info.rect.width, info.rect.height)

    def _clear_selection(self) -> None:
        self.selected = None
        self.apply_button.configure(state=tk.DISABLED)
        self.target_text.set("목록에서 창을 선택하세요.")
        for variable in self.inputs.values():
            variable.set("")

    def _show_target(self, info: WindowInfo) -> None:
        self.selected = info
        self.target_text.set(f"{info.title}  |  HWND 0x{info.hwnd:X}  |  PID {info.pid}")
        for key, variable in self.inputs.items():
            variable.set(str(getattr(info.rect, key)))
        self.apply_button.configure(state=tk.NORMAL)

    def refresh(self) -> None:
        previous = self.selected
        try:
            windows = self.service.list_windows()
        except OSError as error:
            self._clear_selection()
            self.status.set(f"목록 조회 실패: {error}")
            return
        self._clear_selection()
        self.windows = {str(info.hwnd): info for info in windows}
        for item in self.tree.get_children():
            self.tree.delete(item)
        for item, info in self.windows.items():
            self.tree.insert("", tk.END, iid=item, values=self._values(info))
        if previous:
            item = str(previous.hwnd)
            current = self.windows.get(item)
            if current and current.pid == previous.pid:
                self.tree.selection_set(item)
                self.tree.focus(item)
                self.tree.see(item)
                self._show_target(current)
        self.status.set(f"창 {len(windows)}개 / 숨김·도구 창과 이 프로그램은 제외")

    def on_select(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            self._clear_selection()
            return
        target = self.windows.get(selection[0])
        if target is None:
            return
        try:
            current = self.service.read(target)
        except OSError as error:
            self._clear_selection()
            self.status.set(str(error))
            return
        self.windows[selection[0]] = current
        self.tree.item(selection[0], values=self._values(current))
        self._show_target(current)

    def apply(self) -> None:
        target = self.selected
        if target is None:
            return
        try:
            try:
                rect = WindowRect(*(int(self.inputs[key].get())
                                    for key in ("x", "y", "width", "height")))
            except ValueError:
                raise ValueError("X/Y/너비/높이는 정수로 입력하세요.") from None
            self.service.apply(target, rect)
        except (ValueError, OSError) as error:
            self.status.set(f"적용 실패: {error}")
            messagebox.showwarning("위치·크기 적용", str(error), parent=self)
            return
        self.status.set("변경 요청을 보냈습니다. 실제 위치·크기를 확인하는 중…")
        self.apply_button.configure(state=tk.DISABLED)
        self.after(300, lambda: self._verify_apply(target, rect))

    def _verify_apply(self, target: WindowInfo, requested: WindowRect) -> None:
        try:
            current = self.service.read(target)
        except OSError as error:
            if self.selected and self.selected.hwnd == target.hwnd:
                self._clear_selection()
            self.status.set(f"적용 결과 확인 실패: {error}")
            return
        item = str(current.hwnd)
        if self.tree.exists(item):
            self.windows[item] = current
            self.tree.item(item, values=self._values(current))
        if self.selected and (self.selected.hwnd, self.selected.pid) == (target.hwnd, target.pid):
            self._show_target(current)
        if current.rect == requested:
            self.status.set("위치·크기 적용 완료")
        else:
            self.status.set("요청과 실제 위치·크기가 다릅니다. 대상 앱의 크기 제한이나 응답 지연을 확인하세요.")
