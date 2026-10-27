"""客诉改进措施台账 —— 登记、跟踪、有效性验证。

职责边界（2026-10-27 老大确认的闭环方案）：
  - 措施内容与督办状态以「运营工单 pmwb_operation_issue」为准，本台账不重复维护；
  - 本台账只回答三个问题：针对哪个客诉场景、基线多少、降了多少；
  - 到验证周次自动结算 effectiveness，未达标自动标 ineffective（催升级）。

本模块为服务层实现（scripts/complaint/actions.py 是其 CLI 薄封装）；
建运营工单走进程内 operation_issue_service，不走 HTTP 自环。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.complaint import config as C
from services.complaint.ingest import week_key
from services.complaint.metrics import latest_week, week_bounds

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


# 工单大类 → 单号前缀（与前端生成规则一致：BUG-20261027-573 样式）
_ISSUE_NO_PREFIX = {"bug": "BUG", "data": "DATA", "prod": "PROD",
                    "task": "TASK", "complaint": "COMP"}


def _gen_issue_no(db: Session, category: str) -> str:
    """生成运营工单号：前缀-日期-随机序号，撞号重试（原 HTTP 路径缺此逻辑，属修复）。"""
    import random
    prefix = _ISSUE_NO_PREFIX.get(category, "OPS")
    today = datetime.now().strftime("%Y%m%d")
    for _ in range(10):
        no = f"{prefix}-{today}-{random.randint(100, 999)}"
        exists = db.execute(text(
            "SELECT 1 FROM pmwb_operation_issue WHERE issue_no = :no"
        ), {"no": no}).scalar()
        if not exists:
            return no
    raise RuntimeError("运营工单号生成连续撞号，请检查 issue_no 规则")


def _create_issue(db: Session, l1: str, l2: str, title: str, owner: str,
                  due: Optional[date], desc: str) -> Dict:
    """进程内建运营工单（复用 operation_issue_service，不走 HTTP 自环）。"""
    from schemas.operation import OperationIssueCreate
    from services.operation import operation_issue_service

    category, issue_type = _ISSUE_TYPE.get(l1, ("complaint", "other"))
    payload = OperationIssueCreate(
        issue_no=_gen_issue_no(db, category),
        title=title,
        category=category,
        issue_type=issue_type,
        status="pending",
        source="complaint_weekly",
        impact_level="P1",
        handler=owner,
        situation_desc=desc,
        root_cause=f"客诉周报归因：{l1} / {l2}",
        discovery_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        go_live_date=due.strftime("%Y-%m-%d 00:00:00") if due else None,
        root_cause_type="data_issue" if "数据" in l1 else "process_gap",
        impact_scope="platform" if "批量" in desc else "partial_region",
        solution_type="data_repair" if "数据" in l1 else "code_fix",
    )
    obj = operation_issue_service.create(db, payload.model_dump())
    return {"id": obj.id, "issue_no": obj.issue_no}


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
             'planned', :now_ts, :now_ts)
    """), {
        "no": action_no, "title": title, "l1": l1, "l2": l2,
        "iid": issue_id, "ino": issue_no, "owner": owner, "due": due,
        "acc": acceptance, "target": C.DEFAULT_TARGET_DROP_PCT, "vw": C.DEFAULT_VERIFY_WEEKS,
        "now_ts": datetime.now(),
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
                status = :st, updated_at = :now_ts
            WHERE id = :i
        """), {"b": baseline, "l": last_cnt, "d": drop, "st": new_status, "i": a["id"],
               "now_ts": datetime.now()})
        results.append({"action_no": a["action_no"], "l2": l2, "baseline": baseline,
                        "last_week": last_cnt, "drop": drop, "status": new_status})
    db.commit()
    return results


def mark_go_live(db: Session, action_no: str, go_live: date) -> None:
    db.execute(text("""
        UPDATE pmwb_complaint_action
        SET go_live_date = :g, baseline_cnt = :b, status = 'verifying', updated_at = :now_ts
        WHERE action_no = :no
    """), {"g": go_live, "b": baseline_for(db, _l2_of(db, action_no), go_live), "no": action_no,
           "now_ts": datetime.now()})
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


