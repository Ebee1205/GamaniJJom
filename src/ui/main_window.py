"""Tk UI for discovering, selecting and positioning Windows application windows."""
import tkinter as tk
from tkinter import messagebox, ttk

from src.models.window_schema import WindowInfo, WindowRect
from src.services.window_service import WindowService

TITLE_FONT = ("맑은 고딕", 17, "bold")
PLACEHOLDER_TEXT = "목록에서 창을 선택하세요."
HINT_TEXT = ("화면 픽셀·창 바깥 테두리 기준 / 음수 X·Y 지원 / "
             "최소화·최대화 창은 복원 후 적용")
VERIFY_DELAY_MS = 300  # SetWindowPos 는 비동기로 큐에 들어가므로 잠시 후 결과를 확인한다.

# (column id, heading, width)
COLUMNS = (
    ("hwnd", "HWND", 110),
    ("pid", "PID", 75),
    ("title", "제목", 350),
    ("x", "X", 75),
    ("y", "Y", 75),
    ("width", "너비", 75),
    ("height", "높이", 75),
)
# WindowRect 필드 순서와 동일해야 한다.
RECT_FIELDS = (("x", "X"), ("y", "Y"), ("width", "너비"), ("height", "높이"))


class MainWindow(tk.Tk):
    def __init__(self, service: WindowService | None = None) -> None:
        super().__init__()
        self.service = service or WindowService()
        self.windows: dict[str, WindowInfo] = {}  # key: str(hwnd) == Treeview iid
        self.selected: WindowInfo | None = None
        self.inputs: dict[str, tk.StringVar] = {}
        self.target_text = tk.StringVar(value=PLACEHOLDER_TEXT)
        self.status = tk.StringVar(value="창 목록을 읽는 중…")

        self.title("GamaniJJom — 창 위치·크기")
        self.geometry("1050x600")
        self.minsize(820, 450)

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        self._build_toolbar(frame)
        self._build_table(frame)
        self._build_editor(frame)
        self._build_footer(frame)

        self.bind("<F5>", lambda _: self.refresh())
        self.after_idle(self.refresh)

    # ------------------------------------------------------------------ build
    def _build_toolbar(self, parent: ttk.Frame) -> None:
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(toolbar, text="실행 중인 창", font=TITLE_FONT).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="목록 새로고침 (F5)", command=self.refresh).pack(side=tk.RIGHT)

    def _build_table(self, parent: ttk.Frame) -> None:
        table = ttk.Frame(parent)
        table.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(table, columns=[column for column, _, _ in COLUMNS],
                                 show="headings", selectmode="browse")
        for column, label, width in COLUMNS:
            is_title = column == "title"
            self.tree.heading(column, text=label)
            self.tree.column(column, width=width, minwidth=55, stretch=is_title,
                             anchor=tk.W if is_title else tk.E)

        yscroll = ttk.Scrollbar(table, orient=tk.VERTICAL, command=self.tree.yview)
        xscroll = ttk.Scrollbar(table, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

    def _build_editor(self, parent: ttk.Frame) -> None:
        editor = ttk.LabelFrame(parent, text="선택한 창의 위치·크기", padding=12)
        editor.pack(fill=tk.X, pady=(12, 8))
        ttk.Label(editor, textvariable=self.target_text, wraplength=750).grid(
            row=0, column=0, columnspan=9, sticky="w", pady=(0, 8))

        for index, (key, label) in enumerate(RECT_FIELDS):
            ttk.Label(editor, text=label).grid(row=1, column=index * 2, padx=(0, 5))
            variable = tk.StringVar()
            self.inputs[key] = variable
            ttk.Entry(editor, textvariable=variable, width=11).grid(
                row=1, column=index * 2 + 1, padx=(0, 12))

        self.apply_button = ttk.Button(editor, text="위치·크기 적용", command=self.apply,
                                       state=tk.DISABLED)
        self.apply_button.grid(row=1, column=8)

    def _build_footer(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text=HINT_TEXT).pack(anchor=tk.W)
        ttk.Label(parent, textvariable=self.status).pack(anchor=tk.W, pady=(6, 0))

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _row_values(info: WindowInfo) -> tuple:
        rect = info.rect
        return (info.handle_text, info.pid, info.title,
                rect.x, rect.y, rect.width, rect.height)

    def _is_selected(self, info: WindowInfo) -> bool:
        return self.selected is not None and self.selected.identity == info.identity

    def _update_row(self, info: WindowInfo) -> None:
        item = str(info.hwnd)
        if self.tree.exists(item):
            self.windows[item] = info
            self.tree.item(item, values=self._row_values(info))

    def _reload_rows(self, windows: list[WindowInfo]) -> None:
        self.windows = {str(info.hwnd): info for info in windows}
        self.tree.delete(*self.tree.get_children())
        for item, info in self.windows.items():
            self.tree.insert("", tk.END, iid=item, values=self._row_values(info))

    def _clear_selection(self) -> None:
        self.selected = None
        self.apply_button.configure(state=tk.DISABLED)
        self.target_text.set(PLACEHOLDER_TEXT)
        for variable in self.inputs.values():
            variable.set("")

    def _show_target(self, info: WindowInfo) -> None:
        self.selected = info
        self.target_text.set(f"{info.title}  |  HWND {info.handle_text}  |  PID {info.pid}")
        for key, variable in self.inputs.items():
            variable.set(str(getattr(info.rect, key)))
        self.apply_button.configure(state=tk.NORMAL)

    def _restore_selection(self, previous: WindowInfo | None) -> None:
        """새로고침 후에도 같은 창(hwnd+pid)이 남아 있으면 선택을 유지한다."""
        if previous is None:
            return
        item = str(previous.hwnd)
        current = self.windows.get(item)
        if current is None or current.identity != previous.identity:
            return
        self.tree.selection_set(item)
        self.tree.focus(item)
        self.tree.see(item)
        self._show_target(current)

    def _read_rect_inputs(self) -> WindowRect:
        try:
            values = [int(self.inputs[key].get()) for key, _ in RECT_FIELDS]
        except ValueError:
            raise ValueError("X/Y/너비/높이는 정수로 입력하세요.") from None
        return WindowRect(*values)

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