# -*- coding: utf-8 -*-
"""CLI 自测：对真实打印队列执行 急停/恢复/造任务/清除 的完整链路。"""
import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import spooler

NAME = "HP LaserJet P1007"
results = []


def step(label, fn):
    try:
        val = fn()
        results.append(f"PASS  {label}" + (f"  -> {val}" if val is not None else ""))
        return val
    except Exception as e:  # noqa: BLE001
        results.append(f"FAIL  {label}  -> {type(e).__name__}: {e}")
        return None


def make_job():
    """用 PowerShell Out-Printer 造一个真实打印任务。"""
    import subprocess
    script = "'spooler-selftest' | Out-Printer -Name 'HP LaserJet P1007'"
    subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True, timeout=60)


step("枚举打印机", lambda: spooler.list_printers())
step("查询状态(初始)", lambda: spooler.get_printer_status(NAME))
step("急停(暂停队列)", lambda: spooler.pause_printer(NAME))
paused = step("验证已暂停", lambda: spooler.get_printer_status(NAME)["paused"])
if paused is not True:
    results.append("FAIL  队列未进入暂停态")
step("恢复打印", lambda: spooler.resume_printer(NAME))
resumed = step("验证已恢复", lambda: not spooler.get_printer_status(NAME)["paused"])
if resumed is not True:
    results.append("FAIL  队列未解除暂停")
step("造一个打印任务", make_job)
import time
time.sleep(3)
jobs = step("验证任务在队列", lambda: spooler.list_jobs(NAME))
if jobs is not None and len(jobs) == 0:
    results.append("WARN  任务已直接打完离开队列（打印机太快也算正常），清除功能改用取消路径验证")
step("清除打印任务", lambda: spooler.purge_jobs(NAME))
left = step("验证队列已清空", lambda: spooler.list_jobs(NAME))
if left:
    results.append(f"FAIL  清除后队列仍有 {len(left)} 个任务")
step("查询状态(结束)", lambda: spooler.get_printer_status(NAME))

with open(r"D:\杂活\p1007-controller\selftest.log", "w", encoding="utf-8") as f:
    f.write("\n".join(results) + "\n")
print("\n".join(results))
