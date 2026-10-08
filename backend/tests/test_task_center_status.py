"""任务中心就地改状态 + 状态注册表 测试。

覆盖：
  1. 状态注册表核心函数（to_unified / resolve_domain / allowed_next / is_terminal / as_metadata）
  2. 各来源就地改状态成功 + 保留源副作用（进度 / 日期 / 变更日志 / 完成时间）
  3. 流转限制 + 终态锁定（服务端强制，绕过前端也拒绝）
  4. 派生只读来源（需求催办）显式拒绝
  5. 字段级校验（进入处理/完成态需先有责任人）
  6. 元数据端点结构
  7. 「新增状态零数据库迁移」：仅改注册表，新状态即出现在元数据与统一态映射中
"""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from constants import status_registry as sr
from db.models import (
    PmwbActiveOptimization,
    PmwbDevTicket,
    PmwbDevTicketLog,
    PmwbKeyWork,
    PmwbKeyWorkMemberTask,
    PmwbKeyWorkMilestone,
    PmwbMeeting,
    PmwbMeetingAction,
    PmwbOperationIssue,
    PmwbResearchIssue,
    PmwbTodo,
)
from schemas.task_center import TaskStatusUpdateRequest
from services.task_center import task_center_service


# ─────────────────────────────────────────────────────────────
# 构造源数据
# ─────────────────────────────────────────────────────────────
def _add(db, obj):
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def _todo(db, status="todo", **kw):
    return _add(db, PmwbTodo(title=kw.pop("title", "测试待办"), status=status, **kw))


def _op_issue(db, status="pending", handler="张三", **kw):
    return _add(
        db,
        PmwbOperationIssue(
            issue_no=kw.pop("issue_no", "OP-0001"),
            title=kw.pop("title", "测试运营问题"),
            status=status,
            handler=handler,
            **kw,
        ),
    )


def _research(db, status="pending", vendor_handlers="李四", **kw):
    return _add(
        db,
        PmwbResearchIssue(
            issue_no=kw.pop("issue_no", "RS-0001"),
            title=kw.pop("title", "测试调研工单"),
            status=status,
            vendor_handlers=vendor_handlers,
            **kw,
        ),
    )


def _ticket(db, status="created", **kw):
    return _add(
        db,
        PmwbDevTicket(
            ticket_no=kw.pop("ticket_no", "DT-0001"),
            req_id=kw.pop("req_id", "REQ-1"),
            system_name=kw.pop("system_name", "CRM"),
            developer=kw.pop("developer", "王五"),
            status=status,
            **kw,
        ),
    )


def _meeting_action(db, status="pending", **kw):
    meeting = _add(db, PmwbMeeting(meeting_id="M-0001", title="测试会议"))
    return _add(
        db,
        PmwbMeetingAction(
            meeting_id=meeting.id,
            content=kw.pop("content", "测试行动项"),
            owner="赵六",
            status=status,
            **kw,
        ),
    )


def _keywork(db, status="in_progress", **kw):
    return _add(
        db,
        PmwbKeyWork(work_no=kw.pop("work_no", "KW-0001"), title="测试重点工作", status=status),
    )


def _kw_task(db, status="not_started", **kw):
    parent = _keywork(db)
    return _add(
        db,
        PmwbKeyWorkMemberTask(
            key_work_id=parent.id,
            title=kw.pop("title", "成员待办"),
            assignee="孙七",
            status=status,
        ),
    )


def _kw_milestone(db, status="not_started", **kw):
    parent = _keywork(db)
    return _add(
        db,
        PmwbKeyWorkMilestone(
            key_work_id=parent.id, name=kw.pop("name", "里程碑A"), status=status
        ),
    )


def _active_opt(db, status="pending", **kw):
    return _add(db, PmwbActiveOptimization(title=kw.pop("title", "优化建议"), status=status))


def _set(db, source, source_id, status, **kw):
    return task_center_service.update_task_status(
        db, source, source_id, TaskStatusUpdateRequest(status=status, **kw)
    )


# ─────────────────────────────────────────────────────────────
# 1. 注册表核心函数
# ─────────────────────────────────────────────────────────────
def test_registry_core_functions():
    assert sr.to_unified("operation", "verify") == "in_progress"
    assert sr.to_unified("operation", "resolved") == "done"
    assert sr.to_unified("operation", "suspended") == "blocked"
    assert sr.to_unified("ticket", "live") == "done"
    assert sr.to_unified("todo", "cancelled") == "blocked"
    # 自由串容错（会议行动项历史中文值）
    assert sr.to_unified("meeting_action", "进行中") == "in_progress"
    assert sr.to_unified("meeting_action", "已完成") == "done"
    # 未命中兜底
    assert sr.to_unified("operation", "不存在的状态") == "pending"
    # 域解析
    assert sr.resolve_domain("operation_issue") == "operation"
    assert sr.resolve_domain("key_work", "task-1") == "keywork_task"
    assert sr.resolve_domain("key_work", "milestone-9") == "keywork_ms"
    assert sr.resolve_domain("key_work", "7") == "keywork"
    # 流转 / 终态
    assert sr.allowed_next("ticket", "created") == ["design_reviewed"]
    assert sr.is_terminal("operation", "closed") is True
    assert sr.is_terminal("operation", "processing") is False
    # 只读域
    assert sr.is_writable("requirement_urge") is False
    assert sr.is_writable("operation") is True


def test_metadata_endpoint(client: TestClient):
    resp = client.get("/api/v1/meta/status-domains")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert set(data["unified_statuses"]) == {"pending", "in_progress", "done", "blocked"}
    doms = data["domains"]
    for key in ("todo", "operation", "research", "ticket", "meeting_action", "keywork_task"):
        assert key in doms
        assert doms[key]["statuses"], f"{key} 无状态定义"
    op = {s["value"]: s for s in doms["operation"]["statuses"]}
    assert op["closed"]["is_terminal"] is True
    assert op["closed"]["label"] == "已关闭"


# ─────────────────────────────────────────────────────────────
# 2. 各来源就地改状态 + 副作用
# ─────────────────────────────────────────────────────────────
def test_todo_status_change_sets_completed_at(db):
    t = _todo(db, status="todo")
    item = _set(db, "todo", str(t.id), "done")
    assert item.status == "done"
    db.refresh(t)
    assert t.completed_at is not None
    # 终态回退清空 completed_at
    _set(db, "todo", str(t.id), "in_progress")
    db.refresh(t)
    assert t.completed_at is None


def test_operation_status_change_writes_resolve_date(db):
    o = _op_issue(db, status="processing")
    item = _set(db, "operation_issue", str(o.id), "resolved")
    assert item.status == "done"
    assert item.raw_status == "resolved"
    db.refresh(o)
    assert o.resolve_date is not None


def test_research_status_change(db):
    r = _research(db, status="pending")
    item = _set(db, "research_issue", str(r.id), "processing")
    assert item.status == "in_progress"
    db.refresh(r)
    assert r.status == "processing"


def test_dev_ticket_status_change_side_effects(db):
    tk = _ticket(db, status="created")
    item = _set(db, "dev_ticket", str(tk.id), "design_reviewed")
    assert item.status == "in_progress"
    db.refresh(tk)
    assert tk.progress == 20  # STATUS_PROGRESS 副作用
    logs = db.query(PmwbDevTicketLog).filter(PmwbDevTicketLog.ticket_id == tk.id).all()
    assert len(logs) == 1 and logs[0].to_status == "design_reviewed"


def test_meeting_action_status_change(db):
    a = _meeting_action(db, status="pending")
    item = _set(db, "meeting_action", str(a.id), "in_progress")
    assert item.status == "in_progress"
    db.refresh(a)
    assert a.status == "in_progress"


def test_keywork_member_task_status_change(db):
    task = _kw_task(db, status="not_started")
    item = _set(db, "key_work", f"task-{task.id}", "in_progress")
    assert item.status == "in_progress"
    db.refresh(task)
    assert task.status == "in_progress"


def test_keywork_milestone_status_change(db):
    ms = _kw_milestone(db, status="not_started")
    item = _set(db, "key_work", f"milestone-{ms.id}", "completed")
    assert item.status == "done"
    db.refresh(ms)
    assert ms.status == "completed"


def test_active_optimization_status_change(db):
    a = _active_opt(db, status="pending")
    item = _set(db, "active_optimization", str(a.id), "adopted")
    assert item.status == "done"
    db.refresh(a)
    assert a.status == "adopted"


# ─────────────────────────────────────────────────────────────
# 3. 流转限制 + 终态锁定
# ─────────────────────────────────────────────────────────────
def test_invalid_transition_rejected(db):
    tk = _ticket(db, status="created")
    with pytest.raises(Exception) as ei:
        _set(db, "dev_ticket", str(tk.id), "live")  # created 只能到 design_reviewed
    assert "不允许" in str(ei.value)
    db.refresh(tk)
    assert tk.status == "created"  # 未落库


def test_terminal_state_locked(db):
    o = _op_issue(db, status="closed", handler="张三")
    with pytest.raises(Exception) as ei:
        # closed 只允许回退到 resolved
        _set(db, "operation_issue", str(o.id), "processing")
    assert "不允许" in str(ei.value)
    db.refresh(o)
    assert o.status == "closed"


def test_terminal_rollback_allowed(db):
    o = _op_issue(db, status="closed", handler="张三")
    item = _set(db, "operation_issue", str(o.id), "resolved")
    assert item.raw_status == "resolved"


def test_unknown_status_rejected(db):
    t = _todo(db, status="todo")
    with pytest.raises(Exception) as ei:
        _set(db, "todo", str(t.id), "不存在的状态")
    assert "非法状态值" in str(ei.value)


# ─────────────────────────────────────────────────────────────
# 4. 派生只读来源
# ─────────────────────────────────────────────────────────────
def test_requirement_urge_readonly(db):
    with pytest.raises(Exception) as ei:
        _set(db, "requirement_urge", "REQ-1:张三", "done")
    assert "只读" in str(ei.value) or "派生" in str(ei.value)


# ─────────────────────────────────────────────────────────────
# 5. 字段级校验
# ─────────────────────────────────────────────────────────────
def test_required_owner_field(db):
    o = _op_issue(db, status="pending", handler="")  # 无处理人
    with pytest.raises(Exception) as ei:
        _set(db, "operation_issue", str(o.id), "processing")
    assert "处理人" in str(ei.value)
    # 补上处理人后可改
    o.handler = "张三"
    db.commit()
    item = _set(db, "operation_issue", str(o.id), "processing")
    assert item.raw_status == "processing"


# ─────────────────────────────────────────────────────────────
# 6. HTTP 端点
# ─────────────────────────────────────────────────────────────
def test_http_patch_status(client: TestClient, db):
    t = _todo(db, status="todo")
    resp = client.patch(f"/api/v1/task-center/tasks/todo/{t.id}/status", json={"status": "done"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "done"


def test_http_batch_status(client: TestClient, db):
    t1 = _todo(db, status="todo", title="A")
    t2 = _todo(db, status="todo", title="B")
    resp = client.post(
        "/api/v1/task-center/tasks/status/batch",
        json={
            "items": [
                {"source": "todo", "source_id": str(t1.id), "status": "in_progress"},
                {"source": "todo", "source_id": str(t2.id), "status": "不存在的状态"},
            ]
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["updated"] == 1
    assert len(data["errors"]) == 1


# ─────────────────────────────────────────────────────────────
# 7. 新增状态零迁移
# ─────────────────────────────────────────────────────────────
def test_new_status_requires_no_migration(monkeypatch, db):
    """仅在注册表加一个 StatusDef，新状态即：进入元数据 + 可写 + 统一态映射生效。"""
    op = sr.REGISTRY["operation"]
    new_status = sr.StatusDef(
        value="reopened",
        label="重新打开",
        tone="warning",
        unified="in_progress",
        allowed_next=("processing", "resolved"),
    )
    monkeypatch.setitem(sr.REGISTRY, "operation", replace(op, statuses=op.statuses + (new_status,)))

    # 1) 元数据自动暴露（前端徽标/筛选/流转下拉据此渲染，零前端改动）
    meta = sr.as_metadata()
    values = [s["value"] for s in meta["domains"]["operation"]["statuses"]]
    assert "reopened" in values
    # 2) 统一态映射自动生效
    assert sr.to_unified("operation", "reopened") == "in_progress"
    # 3) 写入通道放行（DB 列已是 VARCHAR，无需 ALTER）
    o = _op_issue(db, status="processing", handler="张三")
    o.status = "reopened"
    db.commit()
    db.refresh(o)
    assert o.status == "reopened"


def test_source_row_missing(db):
    with pytest.raises(Exception) as ei:
        _set(db, "todo", "999999", "done")
    assert "不存在" in str(ei.value)
