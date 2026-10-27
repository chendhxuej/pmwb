"""客诉专题分析体系 —— 服务层门面（单一真相源）。

模块一比一镜像自 scripts/complaint（2026-10-27 服务化整合）：
  - config    口径参数唯一来源（阈值/路径/列名映射）
  - classify  分类引擎（字典表 keywords 即口径，进程内缓存）
  - ingest    入库/归档/批量簇与复发派生
  - metrics   12 项周度指标唯一计算实现
  - actions   措施台账（进程内建运营工单，无 HTTP 自环）
  - report    周报 HTML 渲染
  - pipeline  周报一键流水线

scripts/complaint/*.py 仅保留 argparse CLI 薄封装，禁止出现第二份口径实现。
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from constants import status_registry
from services.complaint import actions, classify, config, ingest, metrics, pipeline, report  # noqa: F401
from services.complaint.config import BATCH_DAILY_THRESHOLD, RETENTION_DAYS  # noqa: F401


def get_action(db: Session, action_no: str) -> Optional[Dict]:
    """按单号取措施台账行（任务中心/状态流转用）。"""
    row = db.execute(text(
        "SELECT id, action_no, title, category_l1, category_l2, issue_id, issue_no, "
        "owner, due_date, go_live_date, acceptance, baseline_cnt, target_drop_pct, "
        "verify_weeks, last_week_cnt, actual_drop_pct, status, note, created_at, updated_at "
        "FROM pmwb_complaint_action WHERE action_no = :no"
    ), {"no": action_no}).mappings().first()
    return dict(row) if row else None


def update_status(db: Session, action_no: str, target: str,
                  payload: Optional[Dict] = None) -> Dict:
    """措施状态流转（供任务中心统一端点分派）。

    走 status_registry 校验：
      - 目标状态必须在 allowed_next("complaint_action", current) 白名单内；
      - required_fields（owner / go_live_date）不满足则拒绝并给出提示。
    payload 可携带 owner / go_live_date / note 等补充字段，随流转一并落库。
    """
    payload = payload or {}
    row = get_action(db, action_no)
    if not row:
        raise ValueError(f"措施不存在：{action_no}")

    current = row["status"]
    allowed = status_registry.allowed_next("complaint_action", current)
    if target not in allowed:
        raise ValueError(
            f"状态流转不合法：{current} → {target}（允许：{allowed or '无'}）"
        )

    merged = {**row, **{k: v for k, v in payload.items() if v not in (None, "")}}
    missing = [f for f in status_registry.required_fields("complaint_action", target)
               if not merged.get(f)]
    if missing:
        raise ValueError(f"进入该状态缺必填字段：{', '.join(missing)}")

    sets: List[str] = ["status = :target", "updated_at = :now_ts"]
    params: Dict = {"target": target, "no": action_no,
                    "now_ts": datetime.now()}
    if payload.get("owner"):
        sets.append("owner = :owner")
        params["owner"] = payload["owner"]
    if payload.get("go_live_date"):
        sets.append("go_live_date = :golive")
        params["golive"] = payload["go_live_date"]
    if payload.get("note") is not None:
        sets.append("note = :note")
        params["note"] = payload["note"]
    if target == "verifying" and payload.get("go_live_date") and not row.get("go_live_date"):
        # 首次进入验证期：绑定基线（生效日前 N 周该场景周均单量）
        from datetime import date as _date
        try:
            g = _date.fromisoformat(str(payload["go_live_date"])[:10])
        except ValueError:
            g = None
        if g:
            row["baseline_cnt"] = actions.baseline_for(db, row["category_l2"], g)
            sets.append("baseline_cnt = :baseline")
            params["baseline"] = row["baseline_cnt"]

    db.execute(text(
        f"UPDATE pmwb_complaint_action SET {', '.join(sets)} WHERE action_no = :no"
    ), params)
    db.commit()
    return get_action(db, action_no)


def urge_candidates(db: Session) -> list:
    """督办候选：到期/超期且未完结的措施（邮件 urge-preview 与清单渲染共用）。"""
    from datetime import datetime
    rows = db.execute(text("""
        SELECT action_no, title, category_l2, owner, due_date, status,
               baseline_cnt, last_week_cnt, actual_drop_pct, issue_no
        FROM pmwb_complaint_action
        WHERE status IN ('planned', 'in_progress', 'ineffective')
          AND due_date IS NOT NULL AND due_date < :now
        ORDER BY due_date
    """), {"now": datetime.now()}).mappings().all()
    return [dict(r) for r in rows]
