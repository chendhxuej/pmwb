"""客诉专题分析体系测试。

覆盖（对应 2026-10-27 服务化整合）：
  1. 分类引擎纯逻辑：二级优先、一级兜底、未分类
  2. 状态注册表 complaint_action 域：白名单流转 + required_fields
  3. 措施状态流转 update_status：合法流转、缺责任人拒绝、非法流转拒绝、未知单号拒绝
  4. API：字典列表/启停（清缓存）、台账列表分页与人工校正、措施登记（含字典校验）
  5. 指标空库报 400

说明：metrics/ingest 依赖 MySQL 专有函数（DATE/FIELD/NOW），走真实库由
run_weekly CLI 口径回归覆盖，不在 SQLite 单测范围内。
"""

import pytest
from fastapi.testclient import TestClient

from constants import status_registry as sr
from db.models import PmwbComplaintAction, PmwbComplaintCategory, PmwbComplaintTicket
from services.complaint import update_status
from services.complaint.classify import Dictionary, Rule, UNCLASSIFIED

import re


# ─────────────────────────────────────────────────────────────
# 构造工具
# ─────────────────────────────────────────────────────────────
def _rule(level, parent, name, pattern, sort):
    return Rule(level, parent, name, re.compile(pattern), sort)


def _add(db, obj):
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def _make_action(db, action_no="CACT-2026W44-01", **kw):
    defaults = dict(
        action_no=action_no, title="电视账号同步专项", category_l1="数据与状态异常",
        category_l2="电视与机顶盒账号未同步", owner="", due_date=None,
        acceptance="同类单日峰值降至5单以下", status="planned",
    )
    defaults.update(kw)
    return _add(db, PmwbComplaintAction(**defaults))


def _make_ticket(db, ticket_no="BOMC-001", **kw):
    from datetime import datetime
    defaults = dict(
        ticket_no=ticket_no, week="2026-W44", created_time=datetime(2026, 10, 26, 10, 0),
        city="苏州", content="机顶盒无法激活，显示账号不存在", status="已回复",
        category_l1="数据与状态异常", category_l2="电视与机顶盒账号未同步",
        classify_by="auto", dispatch_count=1,
    )
    defaults.update(kw)
    return _add(db, PmwbComplaintTicket(**defaults))


def _seed_dict(db):
    _add(db, PmwbComplaintCategory(level=1, parent_name=None, name="数据与状态异常",
                                   keywords=r"不同步|未同步|状态不一致", sort_order=10, enabled=1))
    _add(db, PmwbComplaintCategory(level=2, parent_name="数据与状态异常",
                                   name="电视与机顶盒账号未同步",
                                   keywords=r"电视账号|机顶盒", sort_order=11, enabled=1))
    _add(db, PmwbComplaintCategory(level=2, parent_name="数据与状态异常",
                                   name="停用场景", keywords=r"绝不应该命中",
                                   sort_order=12, enabled=0))


# ─────────────────────────────────────────────────────────────
# 1. 分类引擎
# ─────────────────────────────────────────────────────────────
def test_classify_l2_priority_over_l1():
    dic = Dictionary([
        _rule(1, None, "数据与状态异常", r"未同步", 10),
        _rule(2, "数据与状态异常", "电视账号未同步", r"电视账号", 5),
    ])
    l1, l2, hit = dic.classify("电视账号未同步", "")
    assert (l1, l2, hit) == ("数据与状态异常", "电视账号未同步", "电视账号未同步")


def test_classify_l1_fallback_and_unclassified():
    dic = Dictionary([
        _rule(1, None, "流程与工单卡单", r"卡单|未触发", 20),
    ])
    assert dic.classify("施工单未触发", "")[0] == "流程与工单卡单"
    assert dic.classify("随便聊聊", "") == (UNCLASSIFIED, "", "")


def test_classify_l2_map():
    dic = Dictionary([_rule(2, "A类", "场景X", r"x", 1)])
    assert dic.l2_map() == {"场景X": "A类"}


# ─────────────────────────────────────────────────────────────
# 2. 状态注册表 complaint_action 域
# ─────────────────────────────────────────────────────────────
def test_complaint_action_domain_transitions():
    assert sr.resolve_domain("complaint_action") == "complaint_action"
    assert "in_progress" in sr.allowed_next("complaint_action", "planned")
    assert "verifying" in sr.allowed_next("complaint_action", "in_progress")
    # 终态出口：effective 仅允许复验（verifying）；cancelled 允许重新启动；
    # ineffective 允许整改重启或取消
    assert sr.allowed_next("complaint_action", "effective") == ["verifying"]
    assert sr.allowed_next("complaint_action", "cancelled") == ["planned"]
    assert set(sr.allowed_next("complaint_action", "ineffective")) == {"in_progress", "cancelled"}
    assert sr.is_terminal("complaint_action", "effective")
    assert sr.is_terminal("complaint_action", "cancelled")
    # ineffective 可整改重启，非终态
    assert not sr.is_terminal("complaint_action", "ineffective")


def test_complaint_action_required_fields():
    assert "owner" in sr.required_fields("complaint_action", "in_progress")
    assert "go_live_date" in sr.required_fields("complaint_action", "verifying")
    assert sr.required_fields("complaint_action", "planned") == []


def test_complaint_action_to_unified():
    assert sr.to_unified("complaint_action", "planned") == "pending"
    assert sr.to_unified("complaint_action", "in_progress") == "in_progress"
    assert sr.to_unified("complaint_action", "effective") == "done"


# ─────────────────────────────────────────────────────────────
# 3. 措施状态流转
# ─────────────────────────────────────────────────────────────
def test_update_status_unknown_action(db):
    with pytest.raises(ValueError, match="不存在"):
        update_status(db, "CACT-NOPE-99", "in_progress")


def test_update_status_illegal_transition(db):
    _make_action(db, status="effective")
    with pytest.raises(ValueError, match="不合法"):
        update_status(db, "CACT-2026W44-01", "in_progress")


def test_update_status_requires_owner(db):
    _make_action(db, owner="")
    with pytest.raises(ValueError, match="owner|责任人"):
        update_status(db, "CACT-2026W44-01", "in_progress")


def test_update_status_ok_and_go_live(db):
    _make_action(db, owner="吴胜捷")
    row = update_status(db, "CACT-2026W44-01", "in_progress")
    assert row["status"] == "in_progress"
    # verifying 缺生效日 → 拒绝
    with pytest.raises(ValueError, match="go_live_date"):
        update_status(db, "CACT-2026W44-01", "verifying")
    # 补生效日 → 通过且自动绑基线（场景无历史单，基线=0）
    row = update_status(db, "CACT-2026W44-01", "verifying",
                        {"go_live_date": "2026-10-27"})
    assert row["status"] == "verifying"
    assert row["go_live_date"] is not None
    assert row["baseline_cnt"] is not None


# ─────────────────────────────────────────────────────────────
# 4. API
# ─────────────────────────────────────────────────────────────
def test_categories_list_and_toggle(client: TestClient, db):
    _seed_dict(db)
    resp = client.get("/api/v1/complaint/categories")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    items = body["data"]
    assert len(items) == 3
    disabled = next(i for i in items if i["name"] == "停用场景")
    assert disabled["enabled"] == 0

    cid = next(i["id"] for i in items if i["name"] == "停用场景")
    resp = client.put(f"/api/v1/complaint/categories/{cid}/enabled", json={"enabled": 1})
    assert resp.status_code == 200
    assert resp.json()["data"]["enabled"] == 1


def test_tickets_list_and_manual_correction(client: TestClient, db):
    _seed_dict(db)
    t = _make_ticket(db)
    resp = client.get("/api/v1/complaint/tickets", params={"week": "2026-W44"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 1
    item = data["items"][0]
    assert item["ticket_no"] == "BOMC-001"
    assert "机顶盒" in item["content_preview"]
    assert item["classify_by"] == "auto"

    resp = client.put(f"/api/v1/complaint/tickets/{t.id}/category",
                      json={"category_l1": "流程与工单卡单", "category_l2": "",
                            "remark": "人工校正为卡单"})
    assert resp.status_code == 200
    assert resp.json()["data"]["classify_by"] == "manual"

    db.expire_all()
    row = db.query(PmwbComplaintTicket).filter_by(id=t.id).first()
    assert row.classify_by == "manual"
    assert row.category_l1 == "流程与工单卡单"
    assert "人工校正" in (row.remark or "")


def test_create_action_requires_dict_l2(client: TestClient, db):
    resp = client.post("/api/v1/complaint/actions", json={
        "l2": "不存在的场景", "title": "T", "owner": "张三",
        "acceptance": "A",
    })
    assert resp.status_code == 400
    assert "字典" in resp.json()["detail"]


def test_create_action_with_issue_link(client: TestClient, db):
    _seed_dict(db)
    resp = client.post("/api/v1/complaint/actions", json={
        "l2": "电视与机顶盒账号未同步", "title": "电视账号同步专项",
        "owner": "吴胜捷", "due_date": "2026-11-10",
        "acceptance": "同类单日峰值降至5单以下", "desc": "批量", "create_issue": True,
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["action_no"].startswith("CACT-")
    # 进程内建工单成功 → 父子关联完成
    assert data["issue_no"]
    assert data["issue_id"]

    from db.models import PmwbOperationIssue
    issue = db.query(PmwbOperationIssue).filter_by(issue_no=data["issue_no"]).first()
    assert issue is not None
    assert issue.source == "complaint_weekly"
    assert issue.status == "pending"


def test_metrics_empty_db_returns_400(client: TestClient, db):
    resp = client.get("/api/v1/complaint/metrics")
    assert resp.status_code == 400


def test_clusters_empty(client: TestClient, db):
    resp = client.get("/api/v1/complaint/clusters")
    assert resp.status_code == 200
    assert resp.json()["data"]["clusters"] == []
