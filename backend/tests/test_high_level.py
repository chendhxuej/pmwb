"""高级别工单（任务中心子模块）单测 —— 2026-10-15。

覆盖：
- R1/R2/R3/R4 判定矩阵与阈值边界（含 P2 超期、due==today 不算超期、母项继承、人工覆盖）
- levels 级别口径归一（码 / 中文标签 / 需求自由文本 / 未知值宁漏勿错）
- sync 幂等、源终态自动闭环、源消失转已移除
- **采集失败的来源不参与「源消失」判定**（关键护栏，防抖动误标）
- 跟踪态流转合法性（allowed_next / 终态锁定）
- dismiss 移出后自动规则不得复活；lock 锁定不被降级
- 邮件：dry_run 不落真实发送记录、不回写督办次数；confirm_send 逐条落 email_records + urge_count 自增
- 时区：写入时间为 UTC+8（now_cn）

安全：EmailCenterClient.send_email 一律 monkeypatch 为假实现，绝不真发。
"""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from constants import levels
from constants.status_registry import allowed_next
from core.exceptions import NotFoundException, ValidationException
from db.models import (
    EmailRecord,
    PmwbDevTicket,
    PmwbHighLevelTrack,
    PmwbRequirementExt,
    now_cn,
)
from schemas.high_level import (
    HighLevelSendRequest,
    HighLevelTaskQuery,
    HighLevelTrackUpdateRequest,
)
from schemas.task_center import TaskItem, TaskRef
from services import high_level as hl
from services.high_level import DEFAULT_RULE_SET, HighLevelRuleSet, high_level_service
from services.mail_dispatch import EmailCenterClient
from services.task_center import task_center_service
from tests.factories import OperationIssueFactory, TodoFactory
from utils.email import email_client

YESTERDAY = date.today() - timedelta(days=1)
TOMORROW = date.today() + timedelta(days=1)


def _item(source="operation_issue", source_id="1", priority=None, is_overdue=False, **kw):
    return TaskItem(
        task_id=f"{source}:{source_id}",
        source=source,
        source_id=str(source_id),
        priority=priority,
        is_overdue=is_overdue,
        **kw,
    )


# ─────────────────────────────────────────────────────────────
# 1. 级别口径（constants/levels.py）
# ─────────────────────────────────────────────────────────────
def test_levels_normalize_and_high_level():
    assert levels.normalize_priority("P0") == "P0"
    assert levels.normalize_priority("p1") == "P1"
    assert levels.normalize_priority("致命(P0)") == "P0"
    assert levels.normalize_priority("严重(P1)") == "P1"
    assert levels.normalize_priority("一般(P2)") == "P2"
    # 自由文本不映射为码，但仍属高级别
    assert levels.normalize_priority("集团需求") is None
    assert levels.is_high_level("集团需求") is True
    assert levels.is_high_level("紧急需求") is True
    # 未知值宁漏勿错
    assert levels.normalize_priority("随便写的") is None
    assert levels.is_high_level("随便写的") is False
    assert levels.is_high_level(None) is False
    assert levels.is_high_level("P2") is False
    assert levels.is_high_level_label("致命(P0)") is True
    assert levels.is_high_level_label("一般(P2)") is False


def test_levels_rank_order():
    assert levels.level_rank("P0") < levels.level_rank("P1") < levels.level_rank("P2")
    assert levels.level_rank("集团需求") == 0       # 自由文本高级别与 P0 同档
    assert levels.level_rank(None) > levels.level_rank("P3")


# ─────────────────────────────────────────────────────────────
# 2. 判定规则矩阵（R1-R4）
# ─────────────────────────────────────────────────────────────
def test_r1_direct_level():
    j = DEFAULT_RULE_SET.judge(_item(priority="P0"))
    assert j.is_high and j.level_code == "P0" and j.reason == "R1:P0"
    j = DEFAULT_RULE_SET.judge(_item(priority="P1"))
    assert j.is_high and j.reason == "R1:P1"
    # 需求自由文本高级别
    j = DEFAULT_RULE_SET.judge(_item(source="requirement_urge", priority="集团需求"))
    assert j.is_high and j.reason == "R1:集团需求"


def test_r2_overdue_upgrade_and_boundary():
    # P2 超期 → 升格
    j = DEFAULT_RULE_SET.judge(_item(priority="P2", is_overdue=True), overdue_days=5)
    assert j.is_high and j.reason == "R2:overdue:P2:5d"
    # P2 未超期 → 不进池
    assert DEFAULT_RULE_SET.judge(_item(priority="P2", is_overdue=False)).is_high is False
    # P3 超期也不升格（只升 P2）
    assert DEFAULT_RULE_SET.judge(_item(priority="P3", is_overdue=True), overdue_days=99).is_high is False
    # 阈值：超期 0 天但门槛设 3 天 → 不升格
    strict = HighLevelRuleSet(overdue_days_threshold=3)
    assert strict.judge(_item(priority="P2", is_overdue=True), overdue_days=2).is_high is False
    assert strict.judge(_item(priority="P2", is_overdue=True), overdue_days=3).is_high is True
    # dev_ticket 缺 due_date 但库标超期 → 退化标 no-due，仍升格
    j = DEFAULT_RULE_SET.judge(_item(source="dev_ticket", priority="P2", is_overdue=True), overdue_days=None)
    assert j.is_high and j.reason == "R2:overdue:P2:no-due"


def test_r3_inherit_parent():
    j = DEFAULT_RULE_SET.judge(
        _item(source="dev_ticket", priority=None), parent_priority="P0", parent_ref="需求REQ-1"
    )
    assert j.is_high and j.level_code == "P0"
    assert j.reason == "R3:inherit:需求REQ-1(P0)"
    # 母项非高级别 → 不继承
    assert DEFAULT_RULE_SET.judge(
        _item(source="dev_ticket"), parent_priority="P2", parent_ref="需求REQ-2"
    ).is_high is False
    # 关闭继承开关
    no_inherit = HighLevelRuleSet(enable_inherit=False)
    assert no_inherit.judge(
        _item(source="dev_ticket"), parent_priority="P0", parent_ref="r"
    ).is_high is False


def test_r4_manual_override_wins():
    # dismiss 覆盖 P0
    j = DEFAULT_RULE_SET.judge(_item(priority="P0"), manual_override="dismiss")
    assert j.is_high is False and j.reason == "R4:dismiss"
    # lock 覆盖 P3 且不超期
    j = DEFAULT_RULE_SET.judge(_item(priority="P3"), manual_override="lock")
    assert j.is_high is True and j.reason == "R4:lock"
    # escalate 覆盖无级别
    j = DEFAULT_RULE_SET.judge(_item(priority=None), manual_override="escalate")
    assert j.is_high is True and j.reason == "R4:escalate"


# ─────────────────────────────────────────────────────────────
# 3. sync：进池 / 幂等
# ─────────────────────────────────────────────────────────────
def test_sync_pool_and_idempotent(db):
    OperationIssueFactory.create(db, impact_level="P0", status="pending", handler="张三")

    r1 = high_level_service.sync(db)
    assert r1["high"] == 1 and r1["added"] == 1
    assert db.query(PmwbHighLevelTrack).count() == 1
    row = db.query(PmwbHighLevelTrack).first()
    assert row.judge_reason == "R1:P0" and row.track_status == "open"
    assert row.first_seen_at is not None and row.last_seen_at is not None

    first_seen = row.first_seen_at
    r2 = high_level_service.sync(db)
    assert r2["added"] == 0 and r2["updated"] == 1
    assert db.query(PmwbHighLevelTrack).count() == 1
    # 首次纳入时间不被重复刷新
    assert db.query(PmwbHighLevelTrack).first().first_seen_at == first_seen


def test_sync_excludes_requirement_urge_and_low_level(db):
    # 低级别（P2 未超期）不进池
    OperationIssueFactory.create(db, impact_level="P2", status="pending", go_live_date=TOMORROW)
    # 个人待办 P1 进池（级别直判）
    TodoFactory.create(db, priority="P1", status="todo")
    r = high_level_service.sync(db)
    assert r["high"] == 1
    rows = db.query(PmwbHighLevelTrack).all()
    assert len(rows) == 1 and rows[0].source == "todo"


def test_sync_overdue_p2_marked_escalated(db):
    OperationIssueFactory.create(
        db, impact_level="P2", status="processing", handler="李四", go_live_date=YESTERDAY
    )
    r = high_level_service.sync(db)
    assert r["high"] == 1 and r["added"] == 1
    row = db.query(PmwbHighLevelTrack).first()
    assert row.judge_reason.startswith("R2:overdue:P2")
    assert row.track_status == "escalated"     # R2 首次命中自动打「已升级」标
    assert row.first_overdue_at == date.today()


def test_sync_r3_inherit_from_requirement(db):
    PmwbRequirementExt(req_id="REQ-INH-1", status="accepted", priority="P0").__class__  # noqa: B018
    req = PmwbRequirementExt(req_id="REQ-INH-1", status="accepted", priority="P0")
    db.add(req)
    db.add(PmwbDevTicket(
        ticket_no="DEV-INH-1", title="继承高级别的开发单", req_id="REQ-INH-1",
        system_name="订单中心", developer="王五", status="created", priority="P2",
    ))
    db.commit()

    r = high_level_service.sync(db)
    assert r["high"] == 1
    row = db.query(PmwbHighLevelTrack).first()
    assert row.source == "dev_ticket"
    assert row.judge_reason.startswith("R3:inherit:需求REQ-INH-1")
    assert row.level_code == "P0"


# ─────────────────────────────────────────────────────────────
# 4. sync：终态自动闭环 / 源消失 / 失败源护栏
# ─────────────────────────────────────────────────────────────
def test_sync_terminal_source_auto_resolved(db):
    issue = OperationIssueFactory.create(db, impact_level="P0", status="pending", handler="张三")
    high_level_service.sync(db)
    assert db.query(PmwbHighLevelTrack).first().track_status == "open"

    issue.status = "resolved"
    db.commit()
    r = high_level_service.sync(db)
    assert r["resolved"] == 1
    row = db.query(PmwbHighLevelTrack).first()
    assert row.track_status == "resolved" and row.resolved_at is not None

    # 已闭环的终态源不再新建行、不再刷新
    r2 = high_level_service.sync(db)
    assert r2["resolved"] == 0 and r2["added"] == 0


def test_sync_source_gone_marked_dropped(db):
    issue = OperationIssueFactory.create(db, impact_level="P0", status="pending", handler="张三")
    high_level_service.sync(db)

    db.delete(issue)
    db.commit()
    r = high_level_service.sync(db)
    assert r["removed"] == 1
    row = db.query(PmwbHighLevelTrack).first()
    assert row.track_status == "dropped" and row.removed_at is not None and row.is_high == 0


def test_sync_failed_source_never_marks_removed(db, monkeypatch):
    """关键护栏：某来源采集失败时，其工单不得被判为「源消失」。"""
    OperationIssueFactory.create(db, impact_level="P0", status="pending", handler="张三")
    high_level_service.sync(db)
    assert db.query(PmwbHighLevelTrack).count() == 1

    def boom(self, dbs):
        raise RuntimeError("模拟采集抖动")

    monkeypatch.setattr(type(task_center_service), "collect_operation_issue", boom)
    r = high_level_service.sync(db)
    assert "operation_issue" in r["failed_sources"]
    assert r["removed"] == 0
    assert db.query(PmwbHighLevelTrack).first().track_status == "open"


# ─────────────────────────────────────────────────────────────
# 5. 跟踪态流转 / 人工覆盖
# ─────────────────────────────────────────────────────────────
def _seed_one(db, impact_level="P0"):
    issue = OperationIssueFactory.create(db, impact_level=impact_level, status="pending", handler="张三")
    high_level_service.sync(db)
    return db.query(PmwbHighLevelTrack).first(), issue


def test_track_status_transition_and_terminal_lock(db):
    row, _ = _seed_one(db)
    key = (row.source, row.source_id)

    # open → tracking 合法
    high_level_service.update_track(
        db, *key, HighLevelTrackUpdateRequest(track_status="tracking", operator="pmwb")
    )
    assert db.query(PmwbHighLevelTrack).first().track_status == "tracking"

    # tracking → escalated 合法
    high_level_service.update_track(db, *key, HighLevelTrackUpdateRequest(track_status="escalated"))
    assert db.query(PmwbHighLevelTrack).first().track_status == "escalated"

    # escalated → resolved 合法
    high_level_service.update_track(db, *key, HighLevelTrackUpdateRequest(track_status="resolved"))
    assert db.query(PmwbHighLevelTrack).first().resolved_at is not None

    # resolved 为终态，只允许回退到 tracking；直接跳 open 应拒绝
    with pytest.raises(ValidationException):
        high_level_service.update_track(db, *key, HighLevelTrackUpdateRequest(track_status="open"))
    # 合法回退
    high_level_service.update_track(db, *key, HighLevelTrackUpdateRequest(track_status="tracking"))
    assert db.query(PmwbHighLevelTrack).first().track_status == "tracking"


def test_track_update_rejects_unknown_status(db):
    row, _ = _seed_one(db)
    with pytest.raises(ValidationException):
        high_level_service.update_track(
            db, row.source, row.source_id, HighLevelTrackUpdateRequest(track_status="不存在的态")
        )


def test_track_update_missing_row_raises(db):
    with pytest.raises(NotFoundException):
        high_level_service.update_track(
            db, "operation_issue", "999999", HighLevelTrackUpdateRequest(track_status="tracking")
        )


def test_dismiss_not_resurrected_by_sync(db):
    row, _ = _seed_one(db)
    high_level_service.update_track(
        db, row.source, row.source_id, HighLevelTrackUpdateRequest(manual_override="dismiss")
    )
    row = db.query(PmwbHighLevelTrack).first()
    assert row.is_high == 0 and row.track_status == "dropped"

    # 源工单仍是 P0 在途，但人工 dismiss 后自动规则不得复活
    r = high_level_service.sync(db)
    row = db.query(PmwbHighLevelTrack).first()
    assert row.is_high == 0 and row.track_status == "dropped"
    assert r["added"] == 0


def test_lock_protects_from_downgrade(db):
    issue = OperationIssueFactory.create(db, impact_level="P0", status="pending", handler="张三")
    high_level_service.sync(db)
    row = db.query(PmwbHighLevelTrack).first()
    high_level_service.update_track(
        db, row.source, row.source_id, HighLevelTrackUpdateRequest(manual_override="lock")
    )

    # 源级别降为 P2 且不超期（规则不再命中），lock 应保住 is_high=1
    issue.impact_level = "P2"
    issue.go_live_date = TOMORROW
    db.commit()
    high_level_service.sync(db)
    row = db.query(PmwbHighLevelTrack).first()
    assert row.is_high == 1 and row.manual_override == "lock"


# ─────────────────────────────────────────────────────────────
# 6. 列表 / 统计（实时回读源 + 池口径）
# ─────────────────────────────────────────────────────────────
def test_list_tasks_pool_scope_and_source_gone(db):
    _seed_one(db)
    res = high_level_service.list_tasks(db, HighLevelTaskQuery(page=1, page_size=20))
    assert res["total"] == 1
    it = res["items"][0]
    assert it.source == "operation_issue" and it.track_status == "open"
    assert it.owner_display == "张三" and it.level_code == "P0"
    assert it.source_gone is False
    assert it.track_label == "待跟进"

    # 闭环后默认列表不再包含（池口径 = open/tracking/escalated）
    row = db.query(PmwbHighLevelTrack).first()
    high_level_service.update_track(
        db, row.source, row.source_id, HighLevelTrackUpdateRequest(track_status="resolved")
    )
    assert high_level_service.list_tasks(db, HighLevelTaskQuery())["total"] == 0
    assert high_level_service.list_tasks(
        db, HighLevelTaskQuery(include_closed=True)
    )["total"] == 1


def test_list_tasks_source_gone_item(db):
    row, issue = _seed_one(db)
    db.delete(issue)
    db.commit()
    res = high_level_service.list_tasks(db, HighLevelTaskQuery())
    assert res["total"] == 1
    assert res["items"][0].source_gone is True
    assert "源工单已删除" in res["items"][0].title


def test_stats_scope(db):
    _seed_one(db)
    OperationIssueFactory.create(db, impact_level="P2", status="pending", go_live_date=YESTERDAY)
    high_level_service.sync(db)
    st = high_level_service.get_stats(db)
    assert st["total"] == 2
    assert st["escalated"] == 1
    assert st["overdue"] == 1
    assert st["by_source"]["operation_issue"] == 2
    assert st["by_level"]["P0"] == 1 and st["by_level"]["P2"] == 1
    # 责任人分布（按责任人督办单一数据源）：多负责人按人展开
    names = {h["name"]: h["count"] for h in st["by_handler"]}
    assert names.get("张三") == 1 and names.get("测试人") == 1
    assert st["by_handler"][0]["count"] == 1
    assert st["unassigned"] == 0


def test_get_tasks_priority_filter(db):
    """任务中心 get_tasks 新增的 priorities 过滤（大小写不敏感）。"""
    OperationIssueFactory.create(db, impact_level="P0", status="pending", handler="张三")
    OperationIssueFactory.create(db, impact_level="P2", status="pending", handler="李四")
    res = task_center_service.get_tasks(db, source="operation_issue", priorities=["p0"])
    assert res["total"] == 1
    assert res["items"][0].priority == "P0"


# ─────────────────────────────────────────────────────────────
# 7. 邮件督办：dry_run / confirm_send
# ─────────────────────────────────────────────────────────────
def _patch_send(monkeypatch, capture):
    monkeypatch.setattr(
        email_client, "resolve_contact_emails", lambda names: {n: "x@example.com" for n in names}
    )

    def fake_send(self, **kwargs):
        capture.update(kwargs)
        return {"ok": True, "data": {"messageId": "fake-1"}}

    monkeypatch.setattr(EmailCenterClient, "send_email", fake_send)
    monkeypatch.setattr(
        EmailCenterClient, "render_template",
        lambda self, template_id, data: {"subject": "", "body": "", "bodyFormat": "html"},
    )


def _send_req(send_type="urge", confirm=False, dry=False):
    return HighLevelSendRequest(
        tasks=[TaskRef(source="operation_issue", source_id="1")],
        to="test@example.com",
        send_type=send_type,
        dry_run=dry,
        confirm_send=confirm,
        operator="pmwb",
    )


def test_send_dry_run_no_record_no_writeback(db, monkeypatch):
    capture = {}
    _patch_send(monkeypatch, capture)
    row, _ = _seed_one(db)
    # 让 source_id 对齐真实工单 id
    task_ref = TaskRef(source=row.source, source_id=row.source_id)

    res = high_level_service.send(db, HighLevelSendRequest(
        tasks=[task_ref], to="test@example.com", send_type="urge", dry_run=True,
    ))
    assert res["success"] is True and res.get("preview") is True
    assert "高级别工单督办" in res["body"] or "工单" in res["body"]
    # dry_run 不落库、不回写督办次数、不真发
    assert db.query(EmailRecord).count() == 0
    assert db.query(PmwbHighLevelTrack).first().urge_count == 0
    assert capture == {}


def test_send_confirm_writes_records_and_bumps_urge(db, monkeypatch):
    capture = {}
    _patch_send(monkeypatch, capture)
    row, _ = _seed_one(db)
    task_ref = TaskRef(source=row.source, source_id=row.source_id)

    res = high_level_service.send(db, HighLevelSendRequest(
        tasks=[task_ref], to="test@example.com", send_type="urge", confirm_send=True,
    ))
    assert res["success"] is True
    # 主记录 + 逐工单副本，ref_type 统一为 high_level
    recs = db.query(EmailRecord).all()
    assert len(recs) >= 2
    assert all(r.ref_type == "high_level" for r in recs)
    assert any(r.ref_id == f"{row.source}:{row.source_id}" for r in recs)
    # send_email 的收件人统一按列表传入
    assert "test@example.com" in list(capture.get("to") or [])

    bumped = db.query(PmwbHighLevelTrack).first()
    assert bumped.urge_count == 1 and bumped.last_urged_at is not None
    assert bumped.operator == "pmwb"


def test_send_requires_tasks(db):
    with pytest.raises(ValidationException):
        high_level_service.send(db, HighLevelSendRequest(tasks=[], to="test@example.com"))


def test_draft_generates_subject_and_body(db):
    _seed_one(db)
    res = high_level_service.draft(
        db,
        tasks=[{
            "index": 1, "title": "[OPS-1] 一网通开通失败", "source_label": "运营问题",
            "source": "operation_issue", "source_id": "1", "owner": "张三",
            "created_at": "2026-08-01", "due_date": "2026-08-10",
            "status_label": "处理中", "priority": "P0", "description": "客户投诉",
            "is_overdue": True, "is_due_soon": False, "source_url": "",
        }],
        send_type="urge", body=None, recipient_name="张三",
    )
    assert "高级别工单督办" in res["subject"]
    assert "一网通开通失败" in res["subject"]
    assert "优先级" in res["body_md"]


# ─────────────────────────────────────────────────────────────
# 8. 时区（铁律：now_cn / UTC+8）
# ─────────────────────────────────────────────────────────────
def test_sync_writes_cn_timezone(db):
    _seed_one(db)
    row = db.query(PmwbHighLevelTrack).first()
    assert row.created_at is not None
    # now_cn 为 UTC+8 naive；与 UTC now 相差应在 7~9 小时内（避免 UTC 写入）
    delta = abs((now_cn() - row.created_at).total_seconds())
    assert delta < 300
    assert row.created_at.year >= 2026


def test_track_status_domain_registered_and_not_a_source():
    from constants import status_registry as sr
    assert "high_level_track" in sr.REGISTRY
    assert sr.labels_for("high_level_track")["open"] == "待跟进"
    # 刻意不进入 SOURCE_DOMAIN，避免污染任务中心「来源→域」映射
    assert "high_level_track" not in sr.SOURCE_DOMAIN
    assert allowed_next("high_level_track", "open") == ["tracking", "escalated", "resolved", "dropped"]
    assert sr.is_terminal("high_level_track", "resolved") is True
    assert sr.is_terminal("high_level_track", "dropped") is True
    assert sr.is_terminal("high_level_track", "open") is False
    assert sr.is_writable("high_level_track") is True
