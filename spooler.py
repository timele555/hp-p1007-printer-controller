# -*- coding: utf-8 -*-
"""Windows 打印假脱机 (winspool.drv) 薄封装。

提供上位机需要的全部后台能力：
  - 枚举本机打印机
  - 查询队列状态（是否暂停/缺纸/卡纸等）
  - 枚举队列中的打印任务
  - 急停   = SetPrinter(PAUSE)      暂停整个队列，停止送纸
  - 恢复打印 = SetPrinter(RESUME)    恢复队列
  - 清除打印任务 = SetPrinter(PURGE) 删除队列中全部任务（失败时回退为逐个删除）
  - 单个任务的暂停/继续/取消

全部通过 ctypes 直接调用系统 API，无第三方依赖。
"""
from __future__ import annotations

import contextlib
import ctypes
from ctypes import wintypes

_win = ctypes.WinDLL("winspool.drv", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)


class PrinterError(Exception):
    """winspool 调用失败，消息中带系统错误说明。"""


# ---------------- 常量 ----------------
PRINTER_ENUM_LOCAL = 0x00000002
PRINTER_ENUM_CONNECTIONS = 0x00000004

PRINTER_CONTROL_PAUSE = 1
PRINTER_CONTROL_RESUME = 2
PRINTER_CONTROL_PURGE = 3

JOB_CONTROL_PAUSE = 1
JOB_CONTROL_RESUME = 2
JOB_CONTROL_CANCEL = 3
JOB_CONTROL_RESTART = 4

PRINTER_ALL_ACCESS = 0x000F000C
PRINTER_ACCESS_USE = 0x00000008

PRINTER_STATUS_PAUSED = 0x00000001

ERROR_INSUFFICIENT_BUFFER = 122
ERROR_ACCESS_DENIED = 5

JOB_STATUS = {
    0x0001: "已暂停",
    0x0002: "错误",
    0x0004: "正在删除",
    0x0008: "后台处理中",
    0x0010: "正在打印",
    0x0020: "脱机",
    0x0040: "缺纸",
    0x0080: "已打印完",
    0x0100: "已删除",
    0x0200: "被队列阻塞",
    0x0400: "用户干预",
    0x0800: "重新打印",
    0x1000: "已完成",
    0x2000: "保留",
    0x4000: "本地渲染",
}

PRINTER_STATUS = {
    0x00000002: "错误",
    0x00000004: "等待删除",
    0x00000008: "卡纸",
    0x00000010: "缺纸",
    0x00000020: "手动进纸",
    0x00000040: "纸张故障",
    0x00000080: "脱机",
    0x00000100: "I/O 活动中",
    0x00000200: "忙碌",
    0x00000400: "打印中",
    0x00000800: "出纸盒已满",
    0x00001000: "不可用",
    0x00002000: "等待中",
    0x00004000: "处理中",
    0x00008000: "初始化中",
    0x00010000: "预热中",
    0x00020000: "碳粉不足",
    0x00040000: "无碳粉",
    0x00080000: "页面丢弃",
    0x00100000: "需要用户干预",
    0x00400000: "仓门打开",
    0x00800000: "服务器未知",
}


# ---------------- 结构体 ----------------
class PRINTER_INFO_4W(ctypes.Structure):
    _fields_ = [
        ("pPrinterName", wintypes.LPWSTR),
        ("pServerName", wintypes.LPWSTR),
        ("Attributes", wintypes.DWORD),
    ]


class PRINTER_INFO_2W(ctypes.Structure):
    _fields_ = [
        ("pServerName", wintypes.LPWSTR),
        ("pPrinterName", wintypes.LPWSTR),
        ("pShareName", wintypes.LPWSTR),
        ("pPortName", wintypes.LPWSTR),
        ("pDriverName", wintypes.LPWSTR),
        ("pComment", wintypes.LPWSTR),
        ("pLocation", wintypes.LPWSTR),
        ("pDevMode", ctypes.c_void_p),
        ("pSepFile", wintypes.LPWSTR),
        ("pPrintProcessor", wintypes.LPWSTR),
        ("pDatatype", wintypes.LPWSTR),
        ("pParameters", wintypes.LPWSTR),
        ("pSecurityDescriptor", ctypes.c_void_p),
        ("Attributes", wintypes.DWORD),
        ("Priority", wintypes.DWORD),
        ("DefaultPriority", wintypes.DWORD),
        ("StartTime", wintypes.DWORD),
        ("UntilTime", wintypes.DWORD),
        ("Status", wintypes.DWORD),
        ("cJobs", wintypes.DWORD),
        ("AveragePPM", wintypes.DWORD),
    ]


class JOB_INFO_1W(ctypes.Structure):
    _fields_ = [
        ("JobId", wintypes.DWORD),
        ("pName", wintypes.LPWSTR),
        ("pMachineName", wintypes.LPWSTR),
        ("pUserName", wintypes.LPWSTR),
        ("pDocument", wintypes.LPWSTR),
        ("pDatatype", wintypes.LPWSTR),
        ("pStatus", wintypes.LPWSTR),
        ("Status", wintypes.DWORD),
        ("Priority", wintypes.DWORD),
        ("Position", wintypes.DWORD),
        ("TotalPages", wintypes.DWORD),
        ("PagesPrinted", wintypes.DWORD),
        ("DueTime", wintypes.DWORD),
    ]


class PRINTER_DEFAULTSW(ctypes.Structure):
    _fields_ = [
        ("pDatatype", wintypes.LPWSTR),
        ("pDevMode", ctypes.c_void_p),
        ("DesiredAccess", wintypes.DWORD),
    ]


# ---------------- API 原型 ----------------
_win.OpenPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(PRINTER_DEFAULTSW)]
_win.OpenPrinterW.restype = wintypes.BOOL
_win.ClosePrinter.argtypes = [wintypes.HANDLE]
_win.ClosePrinter.restype = wintypes.BOOL
_win.EnumPrintersW.argtypes = [wintypes.DWORD, wintypes.LPWSTR, wintypes.DWORD, ctypes.c_void_p,
                               wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
_win.EnumPrintersW.restype = wintypes.BOOL
_win.EnumJobsW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                           wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
_win.EnumJobsW.restype = wintypes.BOOL
_win.SetPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
_win.SetPrinterW.restype = wintypes.BOOL
_win.SetJobW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
_win.SetJobW.restype = wintypes.BOOL
_win.GetPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
                             wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
_win.GetPrinterW.restype = wintypes.BOOL


# ---------------- 内部工具 ----------------
def _win_err(what: str, code: int | None = None) -> str:
    """生成带系统错误文本的可读错误消息。"""
    if code is None:
        code = ctypes.get_last_error()
    buf = ctypes.create_unicode_buffer(512)
    _kernel32.FormatMessageW(0x00001300, None, code, 0, buf, 512, None)  # FROM_SYSTEM|IGNORE_INSERTS
    sysmsg = (buf.value or "").strip().rstrip(".")
    return f"{what}失败：{sysmsg}（错误码 {code}）"


@contextlib.contextmanager
def open_printer(name: str):
    """打开打印机句柄。先申请管理权限，被拒则降级为使用权限（只能操作自己的任务）。"""
    h = wintypes.HANDLE()
    defaults = PRINTER_DEFAULTSW(None, None, PRINTER_ALL_ACCESS)
    if not _win.OpenPrinterW(name, ctypes.byref(h), ctypes.byref(defaults)):
        err = ctypes.get_last_error()
        if err == ERROR_ACCESS_DENIED:
            defaults.DesiredAccess = PRINTER_ACCESS_USE
            if not _win.OpenPrinterW(name, ctypes.byref(h), ctypes.byref(defaults)):
                raise PrinterError(_win_err("打开打印机", ctypes.get_last_error()))
        else:
            raise PrinterError(_win_err("打开打印机", err))
    try:
        yield h.value
    finally:
        _win.ClosePrinter(h)


def _collect(make_call, struct_type, what: str):
    """两段式枚举：先探缓冲区大小，再真正取数。make_call(buf, size, needed, returned) -> (ok, err)。"""
    size = 0
    for _ in range(3):
        needed = wintypes.DWORD(0)
        returned = wintypes.DWORD(0)
        buf = ctypes.create_string_buffer(size) if size else None
        ok, err = make_call(buf, size, needed, returned)
        if ok:
            if not buf or not returned.value:
                return []
            items = ctypes.cast(buf, ctypes.POINTER(struct_type))
            return [items[i] for i in range(returned.value)]
        if err != ERROR_INSUFFICIENT_BUFFER:
            raise PrinterError(_win_err(what, err))
        size = needed.value
    raise PrinterError(f"{what}失败：缓冲区协商异常")


def job_status_text(pstatus: str | None, flags: int) -> str:
    if pstatus:
        return pstatus
    texts = [t for bit, t in JOB_STATUS.items() if flags & bit]
    return "，".join(texts) if texts else "排队中"


def printer_status_text(status: int) -> str:
    if status == 0:
        return "就绪"
    texts = [t for bit, t in PRINTER_STATUS.items() if status & bit]
    if status & PRINTER_STATUS_PAUSED:
        texts.insert(0, "已暂停")
    return "，".join(texts) if texts else f"未知(0x{status:X})"


# ---------------- 对外接口 ----------------
def list_printers() -> list[str]:
    """返回本机所有打印机（本地 + 网络连接）名称。"""
    def call(buf, size, needed, returned):
        ok = _win.EnumPrintersW(PRINTER_ENUM_LOCAL | PRINTER_ENUM_CONNECTIONS, None, 4,
                                buf, size, ctypes.byref(needed), ctypes.byref(returned))
        return bool(ok), ctypes.get_last_error()
    infos = _collect(call, PRINTER_INFO_4W, "枚举打印机")
    return [i.pPrinterName for i in infos]


def get_printer_status(printer_name: str) -> dict:
    """查询队列状态：是否暂停、系统状态文本、任务数。"""
    with open_printer(printer_name) as h:
        needed = wintypes.DWORD(0)
        _win.GetPrinterW(h, 2, None, 0, ctypes.byref(needed))
        buf = ctypes.create_string_buffer(max(needed.value, 1))
        if not _win.GetPrinterW(h, 2, buf, needed.value, ctypes.byref(needed)):
            raise PrinterError(_win_err("查询打印机状态", ctypes.get_last_error()))
        info = ctypes.cast(buf, ctypes.POINTER(PRINTER_INFO_2W)).contents
    return {
        "raw_status": info.Status,
        "paused": bool(info.Status & PRINTER_STATUS_PAUSED),
        "jobs_count": info.cJobs,
        "text": printer_status_text(info.Status),
    }


def list_jobs(printer_name: str) -> list[dict]:
    """枚举队列中的打印任务。"""
    with open_printer(printer_name) as h:
        def call(buf, size, needed, returned):
            ok = _win.EnumJobsW(h, 0, 512, 1, buf, size,
                                ctypes.byref(needed), ctypes.byref(returned))
            return bool(ok), ctypes.get_last_error()
        infos = _collect(call, JOB_INFO_1W, "枚举打印任务")
    jobs = []
    for j in infos:
        jobs.append({
            "id": j.JobId,
            "document": j.pDocument or j.pName or "",
            "user": j.pUserName or "",
            "status": j.Status,
            "status_text": job_status_text(j.pStatus, j.Status),
            "pages_printed": j.PagesPrinted,
            "total_pages": j.TotalPages,
        })
    return jobs


def pause_printer(printer_name: str) -> None:
    """急停：暂停打印队列，停止向打印机送纸。需要打印机管理权限（通常要管理员）。"""
    with open_printer(printer_name) as h:
        if not _win.SetPrinterW(h, 0, None, PRINTER_CONTROL_PAUSE):
            raise PrinterError(_win_err("暂停打印队列", ctypes.get_last_error()))


def resume_printer(printer_name: str) -> None:
    """恢复打印：解除队列暂停。"""
    with open_printer(printer_name) as h:
        if not _win.SetPrinterW(h, 0, None, PRINTER_CONTROL_RESUME):
            raise PrinterError(_win_err("恢复打印队列", ctypes.get_last_error()))


def purge_jobs(printer_name: str) -> None:
    """清除打印任务：删除队列中的全部任务。PURGE 命令失败时回退为逐个删除。"""
    with open_printer(printer_name) as h:
        if _win.SetPrinterW(h, 0, None, PRINTER_CONTROL_PURGE):
            return
    # 某些驱动/权限组合下 PURGE 命令不可用，回退为逐个删除
    jobs = list_jobs(printer_name)
    if jobs:
        for j in jobs:
            set_job(printer_name, j["id"], JOB_CONTROL_CANCEL)


def set_job(printer_name: str, job_id: int, command: int) -> None:
    """对单个任务执行 暂停/继续/取消（JOB_CONTROL_*）。"""
    with open_printer(printer_name) as h:
        if not _win.SetJobW(h, job_id, 0, None, command):
            raise PrinterError(_win_err("控制打印任务", ctypes.get_last_error()))
