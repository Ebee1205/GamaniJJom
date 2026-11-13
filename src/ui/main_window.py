"""Initial application screen."""
import tkinter as tk
from tkinter import ttk


class MainWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("GamaniJJom")
        self.geometry("800x500")
        self.minsize(520, 320)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        frame = ttk.Frame(self, padding=24)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="GamaniJJom", font=("맑은 고딕", 22, "bold")).pack(anchor=tk.W)
        ttk.Label(frame, text="Windows 창 크기·위치 고정 도구", padding=(0, 8)).pack(anchor=tk.W)
        ttk.Separator(frame).pack(fill=tk.X, pady=16)
        ttk.Label(frame, text="기본 실행 환경이 준비되었습니다.").pack(anchor=tk.W)
        ttk.Label(frame, text="다음 구현: 창 목록 조회 → 위치·크기 변경 → 고정·해제", wraplength=600).pack(anchor=tk.W, pady=12)
        ttk.Button(frame, text="닫기", command=self.destroy).pack(side=tk.BOTTOM, anchor=tk.E)
