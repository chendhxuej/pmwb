# -*- coding: utf-8 -*-
"""周反馈邮件 → 重点工作更新：一键串跑（解析 → 出报告 → 确认 → 落库）。

用法：
    双击 每周邮件更新.bat            # 交互式：出报告后等你按 y
    python run_weekly.py --auto      # 不确认直接落库（给定时任务用）
    python run_weekly.py --dry       # 只出报告，不落库

所有解析/判定/落库都在 `backend/services/keywork_mail_import.py`；
本脚本只做「串流程 + 打印」。收口日由服务写进 pmwb_key_work_mail_import_run 表，
不再用 last_run.txt。

⚠ 更推荐直接开页面：「重点工作」→ 工具栏「从邮件导入」，能逐条勾选、能看存疑。
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = "D:/项目/个人工作台系统/backend/venv/Scripts/python.exe"


def run(script, args=None):
    cmd = [PY, os.path.join(HERE, script)] + (args or [])
    r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stdout[-2000:])
        print(r.stderr[-3000:])
        raise SystemExit("%s 执行失败" % script)
    return r.stdout


def main():
    auto = "--auto" in sys.argv
    dry = "--dry" in sys.argv

    print("=" * 66)
    print("周反馈邮件 → 重点工作更新（与页面「从邮件导入」同一份逻辑）")
    print("=" * 66)

    print("\n[1/3] 解析并匹配系统条目 ...")
    print("  " + run("import_plan.py").strip().splitlines()[0])

    print("\n[2/3] 生成 dry-run 报告 ...")
    print("  " + run("gen_report.py").strip())

    if dry:
        print("\n（--dry：到此为止，未落库）")
        return

    if not auto:
        print("\n请先打开上面的报告过一遍（或直接开页面对照勾选）。")
        ans = input("确认落库？(y/N) ").strip().lower()
        if ans != "y":
            print("已取消，未写库。")
            return

    print("\n[3/3] 落库 ...")
    out = run("apply_import.py", ["--apply"])
    for line in out.strip().splitlines():
        if line.startswith("落库结果") or "失败" in line:
            print("  " + line.strip())
    print("\n提示：例行任务、已完成待联调等条目 CLI 默认跳过；需要改判请用页面导入。")


if __name__ == "__main__":
    main()
