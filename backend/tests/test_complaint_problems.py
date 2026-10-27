"""客诉共性问题闭环管理测试。

覆盖（对应 2026-10-27 共性问题闭环升级）：
  1. 状态注册表 complaint_problem 域：白名单流转 + required_fields + 统一态
  2. 识别规则 R1-R4（批量簇/场景TOP/环比激增/复发）+ 幂等归并
  3. 候选确认：入账/合并/忽略 + 确认前禁关联措施
  4. 问题↔措施多对多：关联/解除/主措施唯一
  5. 措施↔运营工单双向同步：工单解决推措施、缺必填不硬改、source 过滤、
     幂等、go-live 单步推进、effective 置 resolved、递归不死循环、suspended 不动
  6. 闭环建议与重开、归因回写（assign_tickets 优先级）
  7. API：台账/详情/非法流转 400 / 工单按问题下钻
  8. 门禁：任务中心来源仍 9 项（问题不入任务中心）
"""

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from constants import status_registry as sr
from db.models import (
    PmwbComplaintAction,
    PmwbComplaintCategory,
    PmwbComplaintProblem,
    PmwbComplaintTicket,
    PmwbOperationIssue,
)
from schemas.task_center import TASK_SOURCES
from services.complaint import problems as P


# ── 构造工具 ─────────────────────────────────────────────────
def _add(db, obj):
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


L2 = "电视与机顶盒账号未同步"
L2B = "在途单阻塞新业务"


def _seed_dict(db):
    _add(db, PmwbComplaintCategory(level=1, parent_name=None, name="数据与状态异常",
                                   keywords=r"不同步", sort_order=10, enabled=1))
    _add(db, PmwbComplaintCategory(level=2, parent_name="数据与状态异常",
                                   name=L2, keywords=r"机顶盒", sort_order=11, enabled=1))
    _add(db, PmwbComplaintCategory(level=1, parent_name=None, name="流程与工单卡单",
                                   keywords=r"卡单", sort_order=20, enabled=1))
    _add(db, PmwbComplaintCategory(level=2, parent_name="流程与工单卡单",
                                   name=L2B, keywords=r"在途单", sort_order=21, enabled=1))


def _ticket(db, no, l2=L2, day=26, week="2026-W44", **kw):
    defaults = dict(
        ticket_no=no, week=week, created_time=datetime(2026, 10, day, 10, 0),
        city="苏州", content="机顶盒账号异常", status="已回复",
        category_l1="数据与状态异常", category_l2=l2, classify_by="auto",
        dispatch_count=1,
    )
    defaults.update(kw)
    return _add(db, PmwbComplaintTicket(**defaults))


def _action(db, no="CACT-2026W44-01", l2=L2, **kw):
    defaults = dict(
        action_no=no, title="账号同步专项", category_l1="数据与状态异常",
        category_l2=l2, owner="吴胜捷", due_date=date(2026, 11, 6),
        acceptance="周单量降至5以下", status="planned",
    )
    defaults.update(kw)
    return _add(db, PmwbComplaintAction(**defaults))


def _issue(db, no="COMP-20261027-100", source="complaint_weekly", status="pending"):
    return _add(db, PmwbOperationIssue(
        issue_no=no, title="客诉改进工单", category="data", issue_type="data_abnormal",
        status=status, source=source, impact_level="P1", handler="吴胜捷",
    ))


def _candidate(db, no="CPB-2026W44-01", l2=L2, **kw):
    defaults = dict(
        problem_no=no, title=f"{l2}（2026-W44）", category_l1="数据与状态异常",
        category_l2=l2, source_type="batch_cluster", rule_hits="batch_cluster",
        status="candidate", first_week="2026-W44", last_week="2026-W44",
        week_cnt=8, total_cnt=8, peak_cnt=8, active_weeks=1,
    )
    defaults.update(kw)
    return _add(db, PmwbComplaintProblem(**defaults))


# ── 1. 状态机 ────────────────────────────────────────────────
def test_problem_domain_transitions():
    assert sr.get_domain("complaint_problem") is not None
    assert set(sr.allowed_next("complaint_problem", "candidate")) == {"open", "ignored", "merged"}
    assert "resolving" in sr.allowed_next("complaint_problem", "open")
    # 已闭环仅可重开到推进态；merged 终态无出口；ignored 可反悔
    assert sr.allowed_next("complaint_problem", "closed") == ["resolving"]
    assert sr.allowed_next("complaint_problem", "merged") == []
    assert sr.allowed_next("complaint_problem", "ignored") == ["open"]
    assert sr.is_terminal("complaint_problem", "closed")
    assert sr.to_unified("complaint_problem", "merged") == "blocked"


def test_problem_required_fields():
    assert "owner" in sr.required_fields("complaint_problem", "open")
    assert "conclusion" in sr.required_fields("complaint_problem", "closed")
    assert sr.required_fields("complaint_problem", "candidate") == []


def test_problem_to_unified():
    assert sr.to_unified("complaint_problem", "candidate") == "pending"
    assert sr.to_unified("complaint_problem", "resolving") == "in_progress"
    assert sr.to_unified("complaint_problem", "closed") == "done"


# ── 2. 识别规则 ──────────────────────────────────────────────
def test_rule_r1_batch_cluster(db):
    _seed_dict(db)
    for i in range(5):
        _ticket(db, f"B-{i}", day=26, cluster_key=f"{L2}@2026-10-26", is_batch=1)
    _ticket(db, "B-5", day=27)
    _ticket(db, "B-6", day=27)
    _ticket(db, "B-7", day=28)
    r = P.scan_candidates(db, week="2026-W44")
    assert len(r["created"]) == 1
    p = db.query(PmwbComplaintProblem).filter_by(category_l2=L2).one()
    assert p.source_type == "batch_cluster"
    assert "batch_cluster" in p.rule_hits
    # 4 单不触发（日簇不足且周累计不足）
    db.query(PmwbComplaintProblem).delete()
    db.query(PmwbComplaintTicket).delete()
    db.commit()
    for i in range(4):
        _ticket(db, f"C-{i}", day=26, cluster_key=f"{L2}@2026-10-26", is_batch=1)
    r = P.scan_candidates(db, week="2026-W44")
    assert r["created"] == []


def test_rule_r3_surge(db):
    _seed_dict(db)
    # 上周 2 单、本周 6 单（环比 200%）
    for i in range(2):
        _ticket(db, f"P-{i}", day=19, week="2026-W43")
    for i in range(6):
        _ticket(db, f"C-{i}", day=26 + i % 3)  # 3 天各 2 单，日簇不触发
    r = P.scan_candidates(db, week="2026-W44")
    assert len(r["created"]) == 1
    p = db.query(PmwbComplaintProblem).one()
    assert p.source_type == "surge"


def test_rule_r2_top_scene(db):
    _seed_dict(db)
    for i in range(9):  # 3 天各 3 单：周累计达标、日簇不触发
        _ticket(db, f"T-{i}", day=26 + i % 3)
    r = P.scan_candidates(db, week="2026-W44")
    assert len(r["created"]) == 1
    p = db.query(PmwbComplaintProblem).one()
    assert p.source_type == "top_scene"


def test_rule_r4_recur(db):
    _seed_dict(db)
    _action(db, status="effective", go_live_date=date(2026, 10, 20))
    _ticket(db, "R-1", day=27, is_recur=1)
    r = P.scan_candidates(db, week="2026-W44")
    assert len(r["created"]) == 1
    p = db.query(PmwbComplaintProblem).one()
    assert "recur" in p.rule_hits


def test_scan_idempotent_and_unique_per_scene(db):
    _seed_dict(db)
    for i in range(8):
        _ticket(db, f"U-{i}", day=26 + i % 3)
    P.scan_candidates(db, week="2026-W44")
    cnt1 = db.query(PmwbComplaintProblem).count()
    r2 = P.scan_candidates(db, week="2026-W44")
    assert cnt1 == 1 and r2["created"] == []
    assert db.query(PmwbComplaintProblem).count() == 1


# ── 3. 候选确认 ──────────────────────────────────────────────
def test_confirm_open_requires_owner(db):
    p = _candidate(db)
    with pytest.raises(ValueError, match="owner|责任人"):
        P.confirm(db, p.problem_no, "open")


def test_confirm_merge_reassigns_tickets(db):
    _seed_dict(db)
    src = _candidate(db, no="CPB-2026W44-01", l2=L2)
    tgt = _candidate(db, no="CPB-2026W44-02", l2=L2B, status="open", owner="李雷")
    t = _ticket(db, "M-1", l2=L2, problem_no=src.problem_no)
    P.confirm(db, src.problem_no, "merge", merged_into=tgt.problem_no, confirm_by="老大")
    db.expire_all()
    assert db.get(PmwbComplaintTicket, t.id).problem_no == tgt.problem_no
    merged = db.query(PmwbComplaintProblem).filter_by(problem_no=src.problem_no).one()
    assert merged.status == "merged" and merged.merged_into == tgt.problem_no
    assert merged.confirm_by == "老大"


def test_confirm_ignore(db):
    p = _candidate(db)
    t = _ticket(db, "I-1", problem_no=p.problem_no)
    P.confirm(db, p.problem_no, "ignore")
    db.expire_all()
    assert db.query(PmwbComplaintProblem).filter_by(problem_no=p.problem_no).one().status == "ignored"
    assert db.get(PmwbComplaintTicket, t.id).problem_no is None


def test_candidate_cannot_link_action(db):
    p = _candidate(db)
    a = _action(db)
    with pytest.raises(ValueError, match="确认入账"):
        P.link_action(db, p.problem_no, a.action_no)


# ── 4. 多对多 ────────────────────────────────────────────────
def test_link_action_many_to_many_and_primary(db):
    p1 = _candidate(db, no="CPB-2026W44-01", l2=L2, status="open", owner="A")
    p2 = _candidate(db, no="CPB-2026W44-02", l2=L2B, status="open", owner="B")
    a = _action(db)
    P.link_action(db, p1.problem_no, a.action_no, is_primary=True)
    P.link_action(db, p2.problem_no, a.action_no)  # 一措施挂两问题
    assert len(P.linked_actions(db, p1.problem_no)) == 1
    assert len(P.linked_actions(db, p2.problem_no)) == 1
    # 同问题主措施唯一：再挂一条主措施后，主措施数仍为 1
    a2 = _action(db, no="CACT-2026W44-02")
    P.link_action(db, p1.problem_no, a2.action_no, is_primary=True)
    pri = db.query(PmwbComplaintProblem).filter_by(problem_no=p1.problem_no).one()
    _ = pri
    rows = db.execute(
        __import__("sqlalchemy").text(
            "SELECT COUNT(*) FROM pmwb_complaint_problem_action "
            "WHERE problem_no = :p AND is_primary = 1"),
        {"p": p1.problem_no}).scalar()
    assert rows == 1
    # unlink
    P.unlink_action(db, p1.problem_no, a.action_no)
    assert len(P.linked_actions(db, p1.problem_no)) == 1


# ── 5. 双向同步 ──────────────────────────────────────────────
def test_issue_resolved_promotes_action_to_verifying(db):
    a = _action(db, status="in_progress", go_live_date=date(2026, 11, 1))
    issue = _issue(db)
    a.issue_id, a.issue_no = issue.id, issue.issue_no
    db.commit()
    ws = P.after_issue_status(db, issue, "processing", "resolved")
    db.expire_all()
    assert db.query(PmwbComplaintAction).filter_by(action_no=a.action_no).one().status == "verifying"
    assert ws == []


def test_issue_resolved_without_go_live_keeps_action(db):
    a = _action(db, status="in_progress", go_live_date=None)
    issue = _issue(db)
    a.issue_id = issue.id
    db.commit()
    ws = P.after_issue_status(db, issue, "processing", "resolved")
    assert any("待补" in w for w in ws)
    assert db.query(PmwbComplaintAction).filter_by(action_no=a.action_no).one().status == "in_progress"


def test_issue_sync_skips_non_complaint_source(db):
    a = _action(db, status="in_progress", go_live_date=date(2026, 11, 1))
    issue = _issue(db, source="manual")
    a.issue_id = issue.id
    db.commit()
    ws = P.after_issue_status(db, issue, "processing", "resolved")
    assert ws == []
    assert db.query(PmwbComplaintAction).filter_by(action_no=a.action_no).one().status == "in_progress"


def test_issue_sync_idempotent_note(db):
    a = _action(db, status="in_progress", go_live_date=date(2026, 11, 1))
    issue = _issue(db)
    a.issue_id = issue.id
    db.commit()
    P.after_issue_status(db, issue, "processing", "resolved")
    note1 = db.query(PmwbComplaintAction).filter_by(action_no=a.action_no).one().note
    # 重复回调：状态已 verifying，不再流转、不重复写备注
    P.after_issue_status(db, issue, "processing", "resolved")
    db.expire_all()
    row = db.query(PmwbComplaintAction).filter_by(action_no=a.action_no).one()
    assert row.status == "verifying"
    assert row.note.count("[自动同步") == note1.count("[自动同步")


def test_action_go_live_advances_issue_one_step(db):
    a = _action(db, status="in_progress")  # 注册表要求 planned→in_progress 后才能 verifying
    issue = _issue(db, status="pending")
    a.issue_id = issue.id
    db.commit()
    from services.complaint import update_status
    update_status(db, a.action_no, "verifying", {"go_live_date": "2026-10-27"})
    db.expire_all()
    assert db.get(PmwbOperationIssue, issue.id).status == "processing"


def test_action_effective_resolves_issue(db):
    a = _action(db, status="verifying", go_live_date=date(2026, 10, 1))
    issue = _issue(db, status="processing")
    a.issue_id = issue.id
    db.commit()
    from services.complaint import update_status
    update_status(db, a.action_no, "effective")
    db.expire_all()
    assert db.get(PmwbOperationIssue, issue.id).status == "resolved"


def test_sync_no_infinite_loop(db):
    """A 触 B、B 触 A：深度守卫保证有限步终止。"""
    a = _action(db, status="verifying", go_live_date=date(2026, 10, 1))
    issue = _issue(db, status="pending")
    a.issue_id = issue.id
    db.commit()
    from services.complaint import update_status
    update_status(db, a.action_no, "effective")  # 措施生效→工单 resolved；工单联动被深度守卫拦截
    db.expire_all()
    assert db.get(PmwbOperationIssue, issue.id).status == "resolved"


def test_issue_suspended_not_touched(db):
    a = _action(db, status="in_progress", go_live_date=date(2026, 11, 1))
    issue = _issue(db, status="suspended")
    a.issue_id = issue.id
    db.commit()
    ws = P.after_action_status(db, a.action_no, "in_progress", "verifying")
    assert any("挂起" in w for w in ws)
    assert db.get(PmwbOperationIssue, issue.id).status == "suspended"


# ── 6. 归因与闭环 ────────────────────────────────────────────
def test_assign_tickets_priority(db):
    _seed_dict(db)
    bp = _candidate(db, no="CPB-2026W44-01", l2=L2, source_type="batch_cluster",
                    status="open", owner="A")
    t_batch = _ticket(db, "A-1", l2=L2, is_batch=1)
    t_norm = _ticket(db, "A-2", l2=L2)
    r = P.assign_tickets(db, week="2026-W44")
    db.expire_all()
    assert db.get(PmwbComplaintTicket, t_batch.id).problem_no == bp.problem_no
    assert db.get(PmwbComplaintTicket, t_norm.id).problem_no == bp.problem_no


def test_recompute_and_reopen(db):
    _seed_dict(db)
    p = _candidate(db, no="CPB-2026W44-01", l2=L2, status="closed",
                   conclusion="已闭环", closed_week="2026-W43", owner="李雷")
    _ticket(db, "X-1", day=27, is_recur=1)
    P.recompute(db, week="2026-W44")
    db.expire_all()
    row = db.query(PmwbComplaintProblem).filter_by(problem_no=p.problem_no).one()
    assert row.reopen_flag == 1
    # 重开走 registry：closed → resolving（重开清 reopen_flag）
    P.update_status(db, p.problem_no, "resolving")
    db.expire_all()
    row = db.query(PmwbComplaintProblem).filter_by(problem_no=p.problem_no).one()
    assert row.status == "resolving" and row.reopen_flag == 0


def test_closure_suggestions(db):
    _seed_dict(db)
    p = _candidate(db, no="CPB-2026W44-01", l2=L2, status="resolving", owner="A",
                   quiet_weeks=2, recur_weeks=0, week_cnt=2)
    a = _action(db, status="effective", go_live_date=date(2026, 10, 1),
                baseline_cnt=10, target_drop_pct=50)
    P.link_action(db, p.problem_no, a.action_no, is_primary=True, _skip_status_check=True)
    sug = P.closure_suggestions(db)
    assert [s["problem_no"] for s in sug] == [p.problem_no]
    # 复发中 → 不建议闭环
    db.query(PmwbComplaintProblem).filter_by(problem_no=p.problem_no).update({"recur_weeks": 1})
    db.commit()
    assert P.closure_suggestions(db) == []


# ── 7. API ───────────────────────────────────────────────────
def test_problems_list_and_detail(client: TestClient, db):
    _seed_dict(db)
    p = _candidate(db)
    resp = client.get("/api/v1/complaint/problems")
    assert resp.status_code == 200
    assert resp.json()["data"]["items"][0]["problem_no"] == p.problem_no

    resp = client.get(f"/api/v1/complaint/problems/{p.problem_no}")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "candidate"

    resp = client.get("/api/v1/complaint/problems/candidates")
    assert resp.status_code == 200
    assert len(resp.json()["data"]["items"]) == 1


def test_problem_status_illegal_400(client: TestClient, db):
    _seed_dict(db)
    p = _candidate(db)
    resp = client.patch(f"/api/v1/complaint/problems/{p.problem_no}/status",
                        json={"status": "resolving"})
    assert resp.status_code == 400
    assert "不合法" in resp.json()["detail"]


def test_tickets_filter_by_problem_no(client: TestClient, db):
    _seed_dict(db)
    p = _candidate(db)
    _ticket(db, "F-1", problem_no=p.problem_no)
    _ticket(db, "F-2")
    resp = client.get("/api/v1/complaint/tickets", params={"problem_no": p.problem_no})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["ticket_no"] == "F-1"


def test_create_action_with_problem_link(client: TestClient, db):
    _seed_dict(db)
    p = _candidate(db, status="open", owner="张三")
    resp = client.post("/api/v1/complaint/actions", json={
        "l2": L2, "title": "专项措施", "owner": "李雷",
        "acceptance": "周单量≤5", "problem_nos": [p.problem_no],
    })
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["warnings"] == []
    links = P.linked_actions(db, p.problem_no)
    assert len(links) == 1 and links[0]["action_no"] == body["action_no"]


# ── 8. 门禁 ──────────────────────────────────────────────────
def test_task_sources_unchanged():
    """共性问题不入任务中心（可执行单元是措施），来源仍 9 项。"""
    assert len(TASK_SOURCES) == 9
    assert "complaint_problem" not in TASK_SOURCES


def test_operation_issue_update_status_guard(client: TestClient, db):
    """编辑端点收口回归：跳态被 400 拒绝，合法流转仍可用。"""
    issue = _issue(db, status="pending")
    resp = client.put(f"/api/v1/operation/issues/{issue.id}", json={"status": "verify"})
    assert resp.status_code == 400
    assert "不合法" in resp.json()["detail"]
    resp = client.put(f"/api/v1/operation/issues/{issue.id}", json={"status": "processing"})
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "processing"
