"""根因库工具函数测试（rootcause_lib）。

重点覆盖 2026-11-04 实测踩坑：跨簇消重 merge() 迁走工单后，
问题台账/措施的簇锚必须跟随迁移，否则已知判定（known.py 走
「工单簇 → 在办问题簇」匹配）全量失配——实测已知率掉到 0。
"""

from db.models import (
    PmwbComplaintAction,
    PmwbComplaintProblem,
    PmwbComplaintRootcause,
    PmwbComplaintTicket,
)
from services.complaint.rootcause_lib import merge, resolve_merged_no, sync_entity_anchors


def _add(db, obj):
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def _cluster(db, no, title="测试簇", **kw):
    defaults = dict(rootcause_no=no, title=title, status="open", ticket_cnt=0)
    defaults.update(kw)
    return _add(db, PmwbComplaintRootcause(**defaults))


def _ticket(db, no, rc):
    return _add(db, PmwbComplaintTicket(
        ticket_no=no, week="2026-W44", created_time=__import__("datetime").datetime(2026, 10, 26, 10, 0),
        city="苏州", content="x", status="已回复", dispatch_count=1, rootcause_no=rc))


def _problem_row(db, no, rc, rcs):
    from datetime import date
    return _add(db, PmwbComplaintProblem(
        problem_no=no, title="t", rootcause_no=rc, rootcause_nos=rcs,
        status="open", first_week="2026-W44", last_week="2026-W44",
    ))


def _action_row(db, no, rcs):
    from datetime import date
    return _add(db, PmwbComplaintAction(
        action_no=no, title="t", owner="A", due_date=date(2026, 11, 6),
        acceptance="x", status="planned", rootcause_nos=rcs,
    ))


def test_merge_moves_tickets_and_status(db):
    _cluster(db, "RC-A", "主簇")
    _cluster(db, "RC-B", "同义簇")
    t1 = _ticket(db, "T-1", "RC-B")
    t2 = _ticket(db, "T-2", "RC-B")
    r = merge(db, "RC-B", "RC-A")
    db.expire_all()
    assert r["ok"] and r["moved"] == 2
    assert db.get(PmwbComplaintTicket, t1.id).rootcause_no == "RC-A"
    assert db.get(PmwbComplaintTicket, t2.id).rootcause_no == "RC-A"
    src = db.query(PmwbComplaintRootcause).filter_by(rootcause_no="RC-B").one()
    assert src.status == "merged" and src.merged_to == "RC-A"


def test_merge_follows_problem_and_action_anchors(db):
    """消重后问题台账/措施的簇锚必须改指主簇（否则已知判定全失配）。"""
    _cluster(db, "RC-A", "主簇")
    _cluster(db, "RC-B", "同义簇")
    _cluster(db, "RC-C", "另一簇")
    _ticket(db, "T-1", "RC-B")
    p = _problem_row(db, "CPB-1", rc="RC-B", rcs="RC-B,RC-C")
    a = _action_row(db, "CACT-1", rcs="RC-B")

    r = merge(db, "RC-B", "RC-A")
    assert r["ok"]
    db.expire_all()
    row = db.query(PmwbComplaintProblem).filter_by(problem_no="CPB-1").one()
    assert row.rootcause_no == "RC-A"
    assert row.rootcause_nos == "RC-A,RC-C"  # 未受影响的簇保留
    act = db.query(PmwbComplaintAction).filter_by(action_no="CACT-1").one()
    assert act.rootcause_nos == "RC-A"


def test_resolve_merged_no_follows_chain(db):
    """链式合并：B→A、A→D，解析到终簇 D；环与不存在簇安全返回。"""
    _cluster(db, "RC-D", "终簇")
    _cluster(db, "RC-A", "中间簇", status="merged", merged_to="RC-D")
    _cluster(db, "RC-B", "源簇", status="merged", merged_to="RC-A")
    assert resolve_merged_no(db, "RC-B") == "RC-D"
    assert resolve_merged_no(db, "RC-D") == "RC-D"
    assert resolve_merged_no(db, "RC-NOPE") == "RC-NOPE"  # 不存在 → 原样返回


def test_sync_entity_anchors_repairs_legacy_data(db):
    """存量修复：锚点已悬空（锚着 merged 簇）时 sync 可独立跑一次纠偏。"""
    _cluster(db, "RC-A", "主簇")
    _cluster(db, "RC-B", "源簇", status="merged", merged_to="RC-A")
    p = _problem_row(db, "CPB-1", rc="RC-B", rcs="RC-B")
    out = sync_entity_anchors(db)
    db.expire_all()
    assert out["problems"] == 1
    row = db.query(PmwbComplaintProblem).filter_by(problem_no="CPB-1").one()
    assert row.rootcause_no == "RC-A" and row.rootcause_nos == "RC-A"
