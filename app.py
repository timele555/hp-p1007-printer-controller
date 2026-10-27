# -*- coding: utf-8 -*-
"""HP P1007 打印机上位机。

三个核心功能：
  - 清除打印任务：删除队列中所有任务
  - 急停：暂停打印队列（停止送纸，任务保留在队列中）
  - 恢复打印：解除暂停，继续打印

用法：python app.py   （需要与打印机管理员权限一致；建议以管理员运行）
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox

import spooler

REFRESH_MS = 2000  # 队列自动刷新周期


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("HP LaserJet P1007 打印机上位机")
        self.geometry("760x520")
        self.minsize(680, 440)

        self._busy = False          # 防止操作重入
        self._ui_queue: list = []   # 后台线程要回写到 UI 的动作
        self._lock = threading.Lock()

        self._build_ui()
        self.after(150, self._initial_load)
        self.after(REFRESH_MS, self._auto_refresh)

    def _auto_refresh(self):
        """定时自动刷新队列状态与任务列表。"""
        if not self._busy and self.printer_var.get():
            self._spawn(lambda: self._refresh(quiet=True), quiet=True)
        self.after(REFRESH_MS, self._auto_refresh)

    # ---------------- UI ----------------
    def _build_ui(self) -> None:
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(3, weight=1)

        # 第一行：打印机选择 + 状态
        top = ttk.Frame(frm)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(2, weight=1)
        ttk.Label(top, text="打印机：").pack(side=tk.LEFT)
        self.printer_var = tk.StringVar()
        self.printer_box = ttk.Combobox(top, textvariable=self.printer_var, state="readonly", width=32)
        self.printer_box.pack(side=tk.LEFT, padx=(0, 12))
        self.printer_box.bind("<<ComboboxSelected>>", lambda _e: self._spawn(self._refresh))
        self.status_var = tk.StringVar(value="状态：加载中…")
        ttk.Label(top, textvariable=self.status_var).pack(side=tk.LEFT)
        ttk.Button(top, text="刷新", width=8, command=lambda: self._spawn(self._refresh)).pack(side=tk.RIGHT)

        # 第二行：三个功能按钮
        btns = ttk.Frame(frm)
        btns.grid(row=1, column=0, sticky="ew", pady=10)
        for c in range(3):
            btns.columnconfigure(c, weight=1, uniform="btn")
        self.btn_purge = ttk.Button(btns, text="清除打印任务", command=self.on_purge)
        self.btn_pause = ttk.Button(btns, text="急停", command=self.on_pause)
        self.btn_resume = ttk.Button(btns, text="恢复打印", command=self.on_resume)
        self.btn_purge.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.btn_pause.grid(row=0, column=1, sticky="ew", padx=6)
        self.btn_resume.grid(row=0, column=2, sticky="ew", padx=(6, 0))
        hint = ttk.Label(frm, text="急停 = 暂停队列停止送纸（任务保留）；恢复打印 = 解除暂停继续打印；清除打印任务 = 删除队列全部任务",
                         foreground="#666")
        hint.grid(row=2, column=0, sticky="w", pady=(0, 6))

        # 任务列表
        cols = ("id", "doc", "user", "status", "pages")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings", height=9)
        for cid, text, w, anchor in (
            ("id", "任务ID", 70, "center"),
            ("doc", "文档名", 240, "w"),
            ("user", "用户", 90, "w"),
            ("status", "状态", 150, "w"),
            ("pages", "已打印/总页", 100, "center"),
        ):
            self.tree.heading(cid, text=text)
            self.tree.column(cid, width=w, anchor=anchor)
        self.tree.grid(row=3, column=0, sticky="nsew")

        # 单任务操作 + 日志
        bottom = ttk.Frame(frm)
        bottom.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        bottom.columnconfigure(0, weight=1)
        ttk.Label(bottom, text="选中任务：").pack(side=tk.LEFT)
        ttk.Button(bottom, text="暂停", width=8, command=lambda: self.on_job(1)).pack(side=tk.LEFT, padx=3)
        ttk.Button(bottom, text="继续", width=8, command=lambda: self.on_job(2)).pack(side=tk.LEFT, padx=3)
        ttk.Button(bottom, text="取消", width=8, command=lambda: self.on_job(3)).pack(side=tk.LEFT, padx=3)
        self.log_var = tk.StringVar(value="就绪")
        self.log_label = ttk.Label(bottom, textvariable=self.log_var, foreground="#0a5c0a")
        self.log_label.pack(side=tk.LEFT, padx=12)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- 工具 ----------------
    def log(self, msg: str, error: bool = False) -> None:
        self.log_var.set(msg)
        self.log_label.config(foreground="#a00000" if error else "#0a5c0a")

    def _selected_job(self) -> tuple[str, int] | None:
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], "values")
        return self.printer_var.get(), int(vals[0])

    def _spawn(self, fn, *args, quiet: bool = False):
        """把后台工作放进线程，避免 UI 卡死；完成后由 after 回写。

        quiet=True 用于自动刷新，不弹错误框、不禁用按钮、不打扰输入。
        """
        if self._busy:
            return
        self._busy = True
        if not quiet:
            for b in (self.btn_purge, self.btn_pause, self.btn_resume):
                b.state(["disabled"])

        def worker():
            try:
                result, error = fn(), None
            except Exception as e:  # noqa: BLE001 - 界面层兜底所有后台异常
                result, error = None, str(e)
            with self._lock:
                self._ui_queue.append((quiet, result, error))

        threading.Thread(target=worker, daemon=True).start()
        self.after(80, self._drain)

    def _drain(self):
        """从线程收结果并回写 UI。"""
        with self._lock:
            item = self._ui_queue.pop(0) if self._ui_queue else None
        if item is None:
            self.after(80, self._drain)
            return
        quiet, result, error = item
        self._busy = False
        if not quiet:
            for b in (self.btn_purge, self.btn_pause, self.btn_resume):
                b.state(["!disabled"])
            if error:
                self.log(error, error=True)
                messagebox.showerror("操作失败", error)
            elif result:
                self.log(result)
        self._spawn(lambda: self._refresh(quiet=True), quiet=True)

    # ---------------- 后台动作 ----------------
    def _initial_load(self):
        try:
            printers = spooler.list_printers()
        except Exception as e:  # noqa: BLE001
            self.log(str(e), error=True)
            printers = []
        self.printer_box["values"] = printers
        if printers:
            # 优先选 P1007
            pick = next((p for p in printers if "P1007" in p.upper()), printers[0])
            self.printer_var.set(pick)
            self._spawn(lambda: self._refresh(quiet=True), quiet=True)
        else:
            self.status_var.set("状态：未发现打印机")
            self.log("未检测到任何打印机，请确认驱动已安装、打印机已连接", error=True)

    def _refresh(self, quiet: bool = False) -> str:
        name = self.printer_var.get()
        if not name:
            return "未选择打印机"
        st = spooler.get_printer_status(name)
        jobs = spooler.list_jobs(name)
        # 树表重建（保留选中任务 ID 尝试恢复选中）
        sel = self.tree.selection()
        sel_id = self.tree.item(sel[0], "values")[0] if sel else None
        self.tree.delete(*self.tree.get_children())
        for j in jobs:
            pages = f"{j['pages_printed']}/{j['total_pages']}" if j["total_pages"] else str(j["pages_printed"])
            self.tree.insert("", tk.END, values=(j["id"], j["document"], j["user"], j["status_text"], pages))
        if sel_id:
            for item in self.tree.get_children():
                if self.tree.item(item, "values")[0] == sel_id:
                    self.tree.selection_set(item)
                    break
        state = "已暂停" if st["paused"] else st["text"]
        self.status_var.set(f"状态：{state}｜队列任务数：{st['jobs_count']}")
        self.btn_pause.state(["!disabled"] if not st["paused"] else ["disabled"])
        self.btn_resume.state(["!disabled"] if st["paused"] else ["disabled"])
        if not quiet:
            return "已刷新"
        return ""

    # ---------------- 按钮事件 ----------------
    def on_purge(self):
        name = self.printer_var.get()
        if not name:
            messagebox.showwarning("提示", "请先选择打印机")
            return
        if not messagebox.askyesno("确认", f"确定删除打印机「{name}」队列中的全部打印任务？"):
            return
        self._spawn(self._do_purge, name)

    def _do_purge(self, name: str) -> str:
        spooler.purge_jobs(name)
        return f"已清除「{name}」队列中的全部打印任务"

    def on_pause(self):
        name = self.printer_var.get()
        if not name:
            messagebox.showwarning("提示", "请先选择打印机")
            return
        self._spawn(self._do_pause, name)

    def _do_pause(self, name: str) -> str:
        spooler.pause_printer(name)
        return f"急停生效：「{name}」队列已暂停，正在打印的任务将停止送纸"

    def on_resume(self):
        name = self.printer_var.get()
        if not name:
            messagebox.showwarning("提示", "请先选择打印机")
            return
        self._spawn(self._do_resume, name)

    def _do_resume(self, name: str) -> str:
        spooler.resume_printer(name)
        return f"「{name}」已恢复打印"

    def on_job(self, command: int):
        picked = self._selected_job()
        if not picked:
            messagebox.showwarning("提示", "请先在列表中选中一个任务")
            return
        name, job_id = picked
        self._spawn(self._do_job, name, job_id, command)

    def _do_job(self, name: str, job_id: int, command: int) -> str:
        spooler.set_job(name, job_id, command)
        action = {1: "已暂停", 2: "已继续", 3: "已取消"}[command]
        return f"任务 {job_id} {action}"

    def _on_close(self):
        self.destroy()


def _is_admin() -> bool:
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:  # noqa: BLE001
        return False


def _try_elevate() -> None:
    """暂停/清除队列需要打印机管理权限，默认尝试以管理员重启自己；UAC 被拒绝则继续以当前权限运行。"""
    import ctypes
    import sys
    if "--no-elevate" in sys.argv or _is_admin():
        return
    try:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(
            [f'"{p}"' for p in sys.argv] + ["--no-elevate"]), None, 1)
    except Exception:  # noqa: BLE001 - 用户拒绝 UAC 或提权失败
        return
    sys.exit(0)


def main() -> None:
    _try_elevate()
    App().mainloop()


if __name__ == "__main__":
    main()
