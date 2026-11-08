# -*- coding: utf-8 -*-
"""CLI 薄封装：把 diff 结果落库。

**唯一实现是 `backend/services/keywork_mail_import.py::apply_import`**，
与页面「从邮件导入」走完全同一份逻辑（状态只进不退、查重、反馈合并都在服务里）。

用法：
    python apply_import.py            # dry-run：只打印将要做什么
    python apply_import.py --apply    # 真落库

默认跳过：页面提示类（例行任务 / 已完成但正文仍待办）与状态回退被拦的条目——
与页面「默认不勾选」一致，需要覆盖这些请在页面上手动勾。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.abspath(os.path.join(HERE, "..", "..", "backend"))
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)  # core.config 的 env_file 是相对路径 ".env"

from db.base import SessionLocal, engine  # noqa: E402

engine.echo = False  # CLI 不要 SQL 回显（DEBUG=True 时 engine 默认 echo）
from services import keywork_mail_import as svc  # noqa: E402

STATUS_CN = {
    "not_started": "未开始",
    "in_progress": "进行中",
    "completed": "已完成",
    "delayed": "已延期",
    "cancelled": "已作废",
}
KIND_CN = {"month_plan": "月计划", "week_plan": "周计划", "todo": "成员待办"}


def main():
    apply = "--apply" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    db = SessionLocal()
    since = args[0] if args else svc.last_run_date(db)
    until = args[1] if len(args) > 1 else None
    p = svc.build_preview(db, since, until)

    # 与页面默认勾选一致：提示类 + 回退被拦 默认不做
    exclude = [c["key"] for c in p["changes"] if c.get("hint") or c.get("blocked_from")]
    todo_status = [
        c for c in p["changes"] if not c["note_only"] and not c.get("blocked_from") and not c.get("hint")
    ]
    todo_note = [c for c in p["changes"] if c["note_only"] and not c.get("hint")]

    print("=" * 72)
    print("区间：%s → %s　｜　邮件 %d 封" % (p["since"], p["until"], len(p["mails"])))
    print("状态变更 %d／备注 %d／新增 %d／存疑 %d（存疑不落，请在页面裁定）"
          % (len(todo_status), len(todo_note), len(p["adds"]), len(p["doubts"])))
    print("=" * 72)
    for c in todo_status + todo_note:
        tag = "备注" if c["note_only"] else "状态"
        print("  [%s] kw%-2d %-7s #%-4s %s → %s  %s"
              % (tag, c["kw"], KIND_CN[c["kind"]], c["id"],
                 STATUS_CN.get(c["sys_status"], c["sys_status"]),
                 STATUS_CN.get(c["mail_status"], c["mail_status"]),
                 (c.get("note") or "")[:34]))
    for a in p["adds"]:
        print("  [新增] kw%-2d %-7s %-9s %s" % (a["kw"], KIND_CN[a["kind"]], a.get("period") or "", a["title"][:40]))
    for c in p["changes"]:
        if c.get("blocked_from"):
            print("  [拦截] kw%-2d %-7s #%-4s 系统已是「%s」，不回退"
                  % (c["kw"], KIND_CN[c["kind"]], c["id"], STATUS_CN.get(c["blocked_from"], c["blocked_from"])))
    for s in p["duplicates"]:
        print("  [查重跳过] kw%-2d %s" % (s["kw"], s["title"][:48]))

    if not apply:
        print("\n（dry-run，未写库；加 --apply 执行）")
        return

    res = svc.apply_import(db, since, until, exclude=exclude, snapshot_id=p["snapshot_id"], operator="CLI")
    print("\n落库结果：反馈 %d 条／状态 %d 项／备注 %d 项／待办 %d 条／周计划 %d 条／月计划 %d 条／幂等跳过 %d 组"
          % (res["feedback"], res["status"], res["note"], res["task"],
             res["week_plan"], res["month_plan"], res["skipped_feedback"]))
    for f in res.get("failed") or []:
        print("  失败：" + f)


if __name__ == "__main__":
    main()
