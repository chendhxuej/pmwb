# -*- coding: utf-8 -*-
"""CLI 薄封装：把周反馈邮件解析成 diff.json（给 gen_report.py 出报告 / apply_import.py 落库用）。

**唯一实现是 `backend/services/keywork_mail_import.py`**，本文件只负责
「切到 backend 目录 → 调用服务 → 写 diff.json」，禁止在此再写一份解析或匹配逻辑。

用法：
    python import_plan.py                # 从上次收口日解析到今天
    python import_plan.py 2026-10-29     # 指定起点
    python import_plan.py 2026-10-29 2026-11-08   # 指定区间
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.abspath(os.path.join(HERE, "..", "..", "backend"))
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)  # core.config 的 env_file 是相对路径 ".env"，必须在 backend 下才能读到

from db.base import SessionLocal, engine  # noqa: E402

engine.echo = False  # CLI 不要 SQL 回显（DEBUG=True 时 engine 默认 echo）
from services import keywork_mail_import as svc  # noqa: E402


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    db = SessionLocal()
    since = args[0] if args else svc.last_run_date(db)
    until = args[1] if len(args) > 1 else None
    p = svc.build_preview(db, since, until)
    out = {
        "since": p["since"],
        "until": p["until"],
        "snapshot_id": p["snapshot_id"],
        "mails": p["mails"],
        "unmatched_mails": p["unmatched_mails"],
        "changes": p["changes"],
        "adds": p["adds"],
        "duplicates": p["duplicates"],
        "doubts": p["doubts"],
        "summary": p["summary"],
    }
    path = os.path.join(HERE, "diff.json")
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        json.dumps(out, ensure_ascii=False, indent=1, default=str)
    )
    s = p["summary"]
    print(
        "邮件 %d 封；状态变更 %d；备注 %d；新增 %d；存疑 %d；回退被拦 %d；未匹配专题 %d"
        % (
            s["mail_count"],
            s["status_count"],
            s["note_count"],
            s["add_count"],
            s["doubt_count"],
            s["blocked_count"],
            s["unmatched_count"],
        )
    )
    print("diff.json → %s" % path)


if __name__ == "__main__":
    main()
