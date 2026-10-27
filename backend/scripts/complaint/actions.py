"""客诉改进措施台账 —— 登记、跟踪、有效性验证。

职责边界（2026-10-27 老大确认的闭环方案）：
  - 措施内容与督办状态以「运营工单 pmwb_operation_issue」为准，本台账不重复维护；
  - 本台账只回答三个问题：针对哪个客诉场景、基线多少、降了多少；
  - 到验证周次自动结算 effectiveness，未达标自动标 ineffective（催升级）。

用法（backend 目录下）：
    python -m scripts.complaint.actions list
    python -m scripts.complaint.actions add --l2 "电视与机顶盒账号未同步" --title "..." \
        --owner 吴胜捷 --due 2026-11-10 --acceptance "同类单日峰值降至5单以下" --create-issue
    python -m scripts.complaint.actions verify          # 结算所有验证中措施
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence

import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

from scripts.complaint import config as C
from scripts.complaint.ingest import week_key
from scripts.complaint.metrics import latest_week, week_bounds

# 一级性质 → 运营工单子类（保持与运营监控既有枚举一致）
_ISSUE_TYPE = {
    "系统缺陷与办理受阻": ("bug", "bug"),
    "数据与状态异常": ("data", "data_abnormal"),
    "流程与工单卡单": ("bug", "bug"),
    "营销与活动生效异常": ("bug", "bug"),
    "计费与出账争议": ("bug", "bug"),
    "外部依赖与协同": ("complaint", "spot_event"),
    "操作与咨询": ("complaint", "spot_event"),
}


def _next_action_no(db: Session, week: str) -> str:
    prefix = f"CACT-{week.replace('-', '')}-"
    row = db.execute(text(
        "SELECT action_no FROM pmwb_complaint_action WHERE action_no LIKE :p ORDER BY action_no DESC LIMIT 1"
    ), {"p": prefix + "%"}).scalar()
    seq = int(row.split("-")[-1]) + 1 if row else 1
    return f"{prefix}{seq:02d}"


def _create_issue(db: Session, l1: str, l2: str, title: str, owner: str,
                  due: Optional[date], desc: str) -> Dict:
    """通过后端 API 建运营工单（走业务逻辑，不直插库）。"""
    category, issue_type = _ISSUE_TYPE.get(l1, ("complaint", "other"))
    payload = {
        "title": title,
        "category": category,
        "issue_type": issue_type,
        "status": "pending",
        "source": "complaint_weekly",
        "impact_level": "P1",
        "handler": owner,
        "situation_desc": desc,
        "root_cause": f"客诉周报归因：{l1} / {l2}",
        "discovery_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "go_live_date": due.strftime("%Y-%m-%d 00:00:00") if due else None,
        "root_cause_type": "data_issue" if "数据" in l1 else "process_gap",
        "impact_scope": "platform" if "批量" in desc else "partial_region",
        "solution_type": "data_repair" if "数据" in l1 else "code_fix",
    }
    resp = requests.post(f"{C.API_BASE}/operation/issues", json=payload, timeout=10)
    resp.raise_for_status()
    body = resp.json()
    return body.get("data") or {}


def add(db: Session, l2: str, title: str, owner: str, due: Optional[date],
        acceptance: str, create_issue: bool, desc: str = "") -> Dict:
    row = db.execute(text(
        "SELECT parent_name FROM pmwb_complaint_category WHERE level = 2 AND name = :n"
    ), {"n": l2}).scalar()
    if not row:
        raise ValueError(f"二级场景不存在于字典：{l2}（请先在 pmwb_complaint_category 维护）")
    l1 = row

    week = latest_week(db) or week_key(datetime.now())
    action_no = _next_action_no(db, week)

    issue_id = issue_no = None
    if create_issue:
        issue = _create_issue(db, l1, l2, title, owner, due,
                              desc or f"客诉周报（{week}）识别的改进措施，针对场景：{l2}")
        issue_id, issue_no = issue.get("id"), issue.get("issue_no")

    db.execute(text("""
        INSERT INTO pmwb_complaint_action
            (action_no, title, category_l1, category_l2, issue_id, issue_no,
             owner, due_date, acceptance, target_drop_pct, verify_weeks,
             status, created_at, updated_at)
        VALUES
            (:no, :title, :l1, :l2, :iid, :ino, :owner, :due, :acc, :target, :vw,
             'planned', NOW(), NOW())
    """), {
        "no": action_no, "title": title, "l1": l1, "l2": l2,
        "iid": issue_id, "ino": issue_no, "owner": owner, "due": due,
        "acc": acceptance, "target": C.DEFAULT_TARGET_DROP_PCT, "vw": C.DEFAULT_VERIFY_WEEKS,
    })
    db.commit()
    return {"action_no": action_no, "issue_id": issue_id, "issue_no": issue_no, "l1": l1}


def baseline_for(db: Session, l2: str, go_live: date, weeks: int = C.BASELINE_WEEKS) -> float:
    """措施上线前 N 周该场景周均单量。"""
    start = datetime.combine(go_live, datetime.min.time()) - timedelta(weeks=weeks)
    end = datetime.combine(go_live, datetime.min.time())
    cnt = db.execute(text(
        "SELECT COUNT(*) FROM pmwb_complaint_ticket "
        "WHERE category_l2 = :l2 AND created_time >= :s AND created_time < :e"
    ), {"l2": l2, "s": start, "e": end}).scalar() or 0
    return round(cnt / weeks, 1)


def week_count(db: Session, l2: str, week: str) -> int:
    s, e = week_bounds(week)
    return int(db.execute(text(
        "SELECT COUNT(*) FROM pmwb_complaint_ticket "
        "WHERE category_l2 = :l2 AND created_time >= :s AND created_time < :e"
    ), {"l2": l2, "s": s, "e": e}).scalar() or 0)


def verify(db: Session) -> List[Dict]:
    """结算验证中的措施：更新基线/最近一周单量/实际降幅，到观察期满自动定论。"""
    rows = db.execute(text("""
        SELECT id, action_no, category_l2, go_live_date, verify_weeks, baseline_cnt, target_drop_pct, status
        FROM pmwb_complaint_action
        WHERE status IN ('verifying', 'in_progress')
    """)).mappings().all()

    latest = latest_week(db)
    results: List[Dict] = []
    for a in rows:
        l2 = a["category_l2"]
        go_live = a["go_live_date"]
        if not l2 or not go_live:
            continue

        baseline = a["baseline_cnt"] or baseline_for(db, l2, go_live)
        last_cnt = float(week_count(db, l2, latest)) if latest else 0.0
        drop = round((baseline - last_cnt) / baseline * 100, 1) if baseline else None

        elapsed_weeks = (date.today() - go_live).days // 7
        new_status = a["status"]
        if a["status"] == "in_progress" and elapsed_weeks >= 0:
            new_status = "verifying"
        if elapsed_weeks >= (a["verify_weeks"] or C.DEFAULT_VERIFY_WEEKS) and drop is not None:
            new_status = "effective" if drop >= (a["target_drop_pct"] or C.DEFAULT_TARGET_DROP_PCT) else "ineffective"

        db.execute(text("""
            UPDATE pmwb_complaint_action
            SET baseline_cnt = :b, last_week_cnt = :l, actual_drop_pct = :d,
                status = :st, updated_at = NOW()
            WHERE id = :i
        """), {"b": baseline, "l": last_cnt, "d": drop, "st": new_status, "i": a["id"]})
        results.append({"action_no": a["action_no"], "l2": l2, "baseline": baseline,
                        "last_week": last_cnt, "drop": drop, "status": new_status})
    db.commit()
    return results


def mark_go_live(db: Session, action_no: str, go_live: date) -> None:
    db.execute(text("""
        UPDATE pmwb_complaint_action
        SET go_live_date = :g, baseline_cnt = :b, status = 'verifying', updated_at = NOW()
        WHERE action_no = :no
    """), {"g": go_live, "b": baseline_for(db, _l2_of(db, action_no), go_live), "no": action_no})
    db.commit()


def _l2_of(db: Session, action_no: str) -> str:
    return db.execute(text(
        "SELECT category_l2 FROM pmwb_complaint_action WHERE action_no = :no"
    ), {"no": action_no}).scalar() or ""


def list_actions(db: Session) -> List[Dict]:
    rows = db.execute(text("""
        SELECT action_no, category_l1, category_l2, title, owner, due_date, go_live_date,
               baseline_cnt, target_drop_pct, last_week_cnt, actual_drop_pct, status, issue_no
        FROM pmwb_complaint_action
        ORDER BY FIELD(status,'ineffective','verifying','in_progress','planned','effective','cancelled'), due_date
    """)).mappings().all()
    return [dict(r) for r in rows]


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="客诉改进措施台账")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="列出全部措施")

    p_add = sub.add_parser("add", help="登记措施")
    p_add.add_argument("--l2", required=True, help="二级问题场景（须在字典中）")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--owner", required=True)
    p_add.add_argument("--due", help="要求完成日期 YYYY-MM-DD")
    p_add.add_argument("--acceptance", required=True, help="验收标准（可验证）")
    p_add.add_argument("--desc", default="", help="情况说明")
    p_add.add_argument("--create-issue", action="store_true", help="同时在运营监控建工单")

    sub.add_parser("verify", help="结算验证中的措施")

    p_live = sub.add_parser("go-live", help="标记措施生效并绑定基线")
    p_live.add_argument("--action-no", required=True)
    p_live.add_argument("--date", required=True, help="YYYY-MM-DD")

    args = ap.parse_args(argv)

    from db.base import SessionLocal
    db = SessionLocal()
    try:
        if args.cmd == "list":
            items = list_actions(db)
            if not items:
                print("措施台账为空")
                return 0
            print(f"{'编号':<18}{'场景':<24}{'责任人':<10}{'基线':>6}{'上周':>6}{'降幅':>8}  状态")
            for a in items:
                print(f"{a['action_no']:<18}{(a['category_l2'] or '-')[:22]:<24}{a['owner'] or '-':<10}"
                      f"{a['baseline_cnt'] or 0:>6}{a['last_week_cnt'] or 0:>6}"
                      f"{(a['actual_drop_pct'] if a['actual_drop_pct'] is not None else 0):>7}%  {a['status']}")
            return 0

        if args.cmd == "add":
            due = date.fromisoformat(args.due) if args.due else None
            r = add(db, args.l2, args.title, args.owner, due, args.acceptance,
                    args.create_issue, args.desc)
            print(f"已登记措施 {r['action_no']}（{r['l1']} / {args.l2}）")
            if r["issue_no"]:
                print(f"已建运营工单 {r['issue_no']}（id={r['issue_id']}），父子关联完成")
            return 0

        if args.cmd == "verify":
            rs = verify(db)
            if not rs:
                print("无验证中的措施")
                return 0
            for r in rs:
                print(f"{r['action_no']}  {r['l2']}: 基线 {r['baseline']} → 本周 {r['last_week']} "
                      f"（降幅 {r['drop']}%）→ {r['status']}")
            return 0

        if args.cmd == "go-live":
            mark_go_live(db, args.action_no, date.fromisoformat(args.date))
            print(f"{args.action_no} 已标记生效日 {args.date}，进入验证期")
            return 0
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
