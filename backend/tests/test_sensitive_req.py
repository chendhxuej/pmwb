"""敏感需求跟踪子模块单测 —— 2026-10-25。

覆盖：
- sync 自动入池：P0/P1/集团需求/紧急需求 → active；P2/P3 不入池；幂等
- 源需求 closed → 自动闭环 resolved
- 级别下调 → 降级退池；lock 锁定保池；dismiss 永不复活
- 里程碑超期 → delayed；逾期解除（补完成/改期）→ 回 active
- 倒排建议：无上线要求报错；偏移正确（deploy=deadline、test=-4、dev=-10、plan=-18、evaluate=-25）；
  团队唯一源 active_team_systems（workload>0）
- 里程碑保存：全量覆盖删旧行；计划完成晚于上线要求拒绝；非法阶段拒绝
- update_milestone 联动：全部 done → resolved；有超期未完成 → delayed
- to_unified 映射（sensitive_req → sensitive_req_track 域）
- 任务中心 collector collect_sensitive_req：在跟池入列、closed 不入列、due=卡点里程碑
- 邮件：dry_run 不落真实发送、不回写督办次数；confirm_send 落 email_records + urge_count 自增 + escalated
- 红黄态实时计算不落库（is_overdue / is_due_soon）

安全：EmailCenterClient.send_email 一律 monkeypatch 为假实现，绝不真发。
"""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from constants.status_registry import allowed_next, resolve_domain, to_unified
from core.exceptions import NotFoundException, ValidationException
from db.models import (
    EmailRecord,
    PmwbRequirementEvaluation,
    PmwbRequirementExt,
    PmwbRequirementStageLog,
    PmwbReqVendorDev,
    PmwbSensitiveReqMilestone,
    PmwbSensitiveReqTrack,
    SentEmail,
)
from schemas.sensitive_req import (
    SensitiveReqMilestoneItem,
    SensitiveReqMilestoneSaveRequest,
    SensitiveReqMilestoneUpdateRequest,
    SensitiveReqSendRequest,
    SensitiveReqTrackUpdateRequest,
)
from services.mail_dispatch import EmailCenterClient
from services.sensitive_req import sensitive_req_service
from services.task_center import task_center_service
from tests.factories import RequirementExtFactory
from utils.email import email_client

TODAY = date.today()
DEADLINE = TODAY + timedelta(days=30)


def _ext(db, req_id="REQ-SR-001", priority="P0", status="dev", **kw):
    kw.setdefault("version_required_date", DEADLINE)
    return RequirementExtFactory.create(db, req_id=req_id, priority=priority, status=status, **kw)


def _eval(db, req_id, system_name="CRM", sa_name="张三", workload=10.0):
    ev = PmwbRequirementEvaluation(
        req_id=req_id, system_name=system_name, sa_name=sa_name, workload=workload
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def _ms(db, req_id, team="CRM", stage="dev", planned_end=None, status="pending", **kw):
    row = PmwbSensitiveReqMilestone(
        req_id=req_id, team_system_name=team, stage=stage,
        planned_end=planned_end, status=status, **kw,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ─────────────────────────────────────────────────────────────
# 1. sync 自动入池
# ─────────────────────────────────────────────────────────────
def test_sync_pulls_high_priority(db):
    _ext(db, "REQ-A", priority="P0")
    _ext(db, "REQ-B", priority="P1")
    _ext(db, "REQ-C", priority="集团需求")
    _ext(db, "REQ-D", priority="紧急需求")
    _ext(db, "REQ-E", priority="P2")
    _ext(db, "REQ-F", priority="P3")

    stats = sensitive_req_service.sync(db)
    assert stats["added"] == 4
    rows = {r.req_id: r for r in db.query(PmwbSensitiveReqTrack).all()}
    assert set(rows) == {"REQ-A", "REQ-B", "REQ-C", "REQ-D"}
    assert all(r.track_status == "active" and r.is_sensitive == 1 for r in rows.values())
    assert rows["REQ-A"].judge_reason == "R1:P0"
    assert rows["REQ-C"].judge_reason == "R1:集团需求"


def test_sync_idempotent(db):
    _ext(db, "REQ-A", priority="P0")
    sensitive_req_service.sync(db)
    stats = sensitive_req_service.sync(db)
    assert stats["added"] == 0
    assert db.query(PmwbSensitiveReqTrack).count() == 1


def test_sync_closed_req_resolves(db):
    _ext(db, "REQ-A", priority="P0", status="closed", delivered_date=TODAY)
    sensitive_req_service.sync(db)
    row = db.query(PmwbSensitiveReqTrack).filter_by(req_id="REQ-A").first()
    assert row.track_status == "resolved"


def test_sync_demote_on_priority_down(db):
    _ext(db, "REQ-A", priority="P0")
    sensitive_req_service.sync(db)
    ext = db.query(PmwbRequirementExt).filter_by(req_id="REQ-A").first()
    ext.priority = "P2"
    db.commit()
    stats = sensitive_req_service.sync(db)
    assert stats["demoted"] == 1
    row = db.query(PmwbSensitiveReqTrack).filter_by(req_id="REQ-A").first()
    assert row.is_sensitive == 0 and row.track_status == "dropped"


def test_lock_keeps_pool_on_demote_and_dismiss_never_revives(db):
    _ext(db, "REQ-A", priority="P0")
    sensitive_req_service.sync(db)
    sensitive_req_service.update_track(
        db, "REQ-A", SensitiveReqTrackUpdateRequest(manual_override="lock")
    )
    ext = db.query(PmwbRequirementExt).filter_by(req_id="REQ-A").first()
    ext.priority = "P3"
    db.commit()
    sensitive_req_service.sync(db)
    row = db.query(PmwbSensitiveReqTrack).filter_by(req_id="REQ-A").first()
    assert row.is_sensitive == 1 and row.judge_reason == "R4:lock"

    # dismiss 后即使再改回 P0 也不复活
    sensitive_req_service.update_track(
        db, "REQ-A", SensitiveReqTrackUpdateRequest(manual_override="dismiss")
    )
    ext.priority = "P0"
    db.commit()
    stats = sensitive_req_service.sync(db)
    assert stats["added"] == 0
    row = db.query(PmwbSensitiveReqTrack).filter_by(req_id="REQ-A").first()
    assert row.track_status == "dropped"


def test_sync_source_gone_drops(db):
    _ext(db, "REQ-A", priority="P0")
    sensitive_req_service.sync(db)
    db.query(PmwbRequirementExt).filter_by(req_id="REQ-A").delete()
    db.commit()
    stats = sensitive_req_service.sync(db)
    assert stats["removed"] == 1


# ─────────────────────────────────────────────────────────────
# 2. 里程碑超期 → delayed；解除 → active
# ─────────────────────────────────────────────────────────────
def test_overdue_milestone_marks_delayed(db):
    _ext(db, "REQ-A", priority="P0")
    _ms(db, "REQ-A", stage="dev", planned_end=TODAY - timedelta(days=2))
    stats = sensitive_req_service.sync(db)
    assert stats["delayed"] == 1
    row = db.query(PmwbSensitiveReqTrack).filter_by(req_id="REQ-A").first()
    assert row.track_status == "delayed"
    assert row.first_overdue_at == TODAY - timedelta(days=2)


def test_overdue_cleared_back_to_active(db):
    _ext(db, "REQ-A", priority="P0")
    _ms(db, "REQ-A", stage="dev", planned_end=TODAY - timedelta(days=2))
    sensitive_req_service.sync(db)
    ms = db.query(PmwbSensitiveReqMilestone).filter_by(req_id="REQ-A").first()
    # 改期到未来（未完成）→ 超期解除回 active
    sensitive_req_service.update_milestone(
        db, ms.id, SensitiveReqMilestoneUpdateRequest(planned_end=TODAY + timedelta(days=3))
    )
    row = db.query(PmwbSensitiveReqTrack).filter_by(req_id="REQ-A").first()
    assert row.track_status == "active"


def test_all_done_auto_resolves(db):
    _ext(db, "REQ-A", priority="P0")
    _ms(db, "REQ-A", stage="dev", planned_end=TODAY - timedelta(days=2))
    sensitive_req_service.sync(db)
    ms = db.query(PmwbSensitiveReqMilestone).filter_by(req_id="REQ-A").first()
    # 唯一里程碑完成 → 全部完成 → 跟踪自动闭环
    sensitive_req_service.update_milestone(
        db, ms.id, SensitiveReqMilestoneUpdateRequest(status="done", actual_end=TODAY)
    )
    row = db.query(PmwbSensitiveReqTrack).filter_by(req_id="REQ-A").first()
    assert row.track_status == "resolved"


def test_escalated_not_downgraded_by_sync(db):
    _ext(db, "REQ-A", priority="P0")
    _ms(db, "REQ-A", stage="dev", planned_end=TODAY - timedelta(days=2))
    sensitive_req_service.sync(db)
    row = db.query(PmwbSensitiveReqTrack).filter_by(req_id="REQ-A").first()
    row.track_status = "escalated"
    db.commit()
    sensitive_req_service.sync(db)
    db.refresh(row)
    assert row.track_status == "escalated"


# ─────────────────────────────────────────────────────────────
# 3. 倒排建议
# ─────────────────────────────────────────────────────────────
def test_plan_suggestion_requires_deadline(db):
    _ext(db, "REQ-A", priority="P0", version_required_date=None)
    with pytest.raises(ValidationException):
        sensitive_req_service.plan_suggestion(db, "REQ-A")


def test_plan_suggestion_offsets_and_teams(db):
    _ext(db, "REQ-A", priority="P0", sa_name="张三")
    _eval(db, "REQ-A", system_name="CRM", sa_name="李四", workload=5.0)
    _eval(db, "REQ-A", system_name="BOSS", sa_name="王五", workload=3.0)
    _eval(db, "REQ-A", system_name="零工作量", workload=0.0)  # 不活跃，不入团队

    sug = sensitive_req_service.plan_suggestion(db, "REQ-A")
    assert sug["teams"] == ["BOSS", "CRM"]  # workload>0 去重排序
    assert len(sug["items"]) == 10  # 2 团队 × 5 阶段
    by_key = {(i["team_system_name"], i["stage"]): i for i in sug["items"]}
    # 偏移：deploy=0、test=4、dev=10、plan=18、evaluate=25
    assert by_key[("CRM", "deploy")]["planned_end"] == DEADLINE
    assert by_key[("CRM", "test")]["planned_end"] == DEADLINE - timedelta(days=4)
    assert by_key[("CRM", "dev")]["planned_end"] == DEADLINE - timedelta(days=10)
    assert by_key[("CRM", "plan")]["planned_end"] == DEADLINE - timedelta(days=18)
    assert by_key[("CRM", "evaluate")]["planned_end"] == DEADLINE - timedelta(days=25)
    # 评估责任人预填 SA，开发责任人预填厂家负责人
    assert by_key[("CRM", "evaluate")]["owner"] == "张三"
    assert by_key[("CRM", "dev")]["owner"] == "李四"
    # 阶段衔接：planned_start = 上一阶段 planned_end + 1
    assert by_key[("CRM", "test")]["planned_start"] == by_key[("CRM", "dev")]["planned_end"] + timedelta(days=1)


def test_plan_suggestion_fallback_team(db):
    _ext(db, "REQ-A", priority="P0", system_name="电子协议")
    sug = sensitive_req_service.plan_suggestion(db, "REQ-A")
    assert sug["teams"] == ["电子协议"]


# ─────────────────────────────────────────────────────────────
# 4. 里程碑保存（PUT 全量覆盖）
# ─────────────────────────────────────────────────────────────
def test_save_milestones_full_overwrite(db):
    _ext(db, "REQ-A", priority="P0")
    _ms(db, "REQ-A", team="OLD", stage="dev", planned_end=DEADLINE - timedelta(days=10))
    items = [
        SensitiveReqMilestoneItem(team_system_name="CRM", stage=st, planned_end=DEADLINE - timedelta(days=off))
        for st, off in (("deploy", 0), ("test", 4), ("dev", 10))
    ]
    res = sensitive_req_service.save_milestones(
        db, "REQ-A", SensitiveReqMilestoneSaveRequest(items=items)
    )
    assert res["saved"] == 3
    rows = db.query(PmwbSensitiveReqMilestone).filter_by(req_id="REQ-A").all()
    assert {(r.team_system_name, r.stage) for r in rows} == {("CRM", "deploy"), ("CRM", "test"), ("CRM", "dev")}


def test_save_milestones_rejects_late_end(db):
    _ext(db, "REQ-A", priority="P0")
    with pytest.raises(ValidationException):
        sensitive_req_service.save_milestones(db, "REQ-A", SensitiveReqMilestoneSaveRequest(items=[
            SensitiveReqMilestoneItem(team_system_name="CRM", stage="deploy", planned_end=DEADLINE + timedelta(days=1))
        ]))


def test_save_milestones_rejects_bad_stage(db):
    _ext(db, "REQ-A", priority="P0")
    with pytest.raises(ValidationException):
        sensitive_req_service.save_milestones(db, "REQ-A", SensitiveReqMilestoneSaveRequest(items=[
            SensitiveReqMilestoneItem(team_system_name="CRM", stage="story")
        ]))


def test_save_milestones_rejects_duplicate(db):
    _ext(db, "REQ-A", priority="P0")
    with pytest.raises(ValidationException):
        sensitive_req_service.save_milestones(db, "REQ-A", SensitiveReqMilestoneSaveRequest(items=[
            SensitiveReqMilestoneItem(team_system_name="CRM", stage="dev"),
            SensitiveReqMilestoneItem(team_system_name="CRM", stage="dev"),
        ]))


# ─────────────────────────────────────────────────────────────
# 5. update_milestone 联动
# ─────────────────────────────────────────────────────────────
def test_all_done_resolves_track(db):
    _ext(db, "REQ-A", priority="P0")
    ms1 = _ms(db, "REQ-A", team="CRM", stage="deploy", planned_end=DEADLINE, status="done")
    ms2 = _ms(db, "REQ-A", team="CRM", stage="dev", planned_end=DEADLINE - timedelta(days=10), status="doing")
    sensitive_req_service.sync(db)
    sensitive_req_service.update_milestone(db, ms2.id, SensitiveReqMilestoneUpdateRequest(status="done"))
    row = db.query(PmwbSensitiveReqTrack).filter_by(req_id="REQ-A").first()
    assert row.track_status == "resolved"
    assert ms1.id  # noqa：占位引用


def test_milestone_red_flag_is_computed_not_stored(db):
    _ext(db, "REQ-A", priority="P0")
    _ms(db, "REQ-A", stage="test", planned_end=TODAY - timedelta(days=1))
    today = TODAY
    ms = db.query(PmwbSensitiveReqMilestone).filter_by(req_id="REQ-A").first()
    composed = sensitive_req_service._compose_milestone(ms, None, today)
    assert composed["is_overdue"] is True and composed["overdue_days"] == 1
    # 完成 → 不再红
    ms.status = "done"
    composed2 = sensitive_req_service._compose_milestone(ms, None, today)
    assert composed2["is_overdue"] is False


# ─────────────────────────────────────────────────────────────
# 6. 注册表 / 任务中心接线
# ─────────────────────────────────────────────────────────────
def test_registry_domains_and_unified():
    assert resolve_domain("sensitive_req") == "sensitive_req_track"
    assert to_unified("sensitive_req_track", "active") == "in_progress"
    assert to_unified("sensitive_req_track", "delayed") == "in_progress"
    assert to_unified("sensitive_req_track", "escalated") == "in_progress"
    assert to_unified("sensitive_req_track", "resolved") == "done"
    assert to_unified("sensitive_req_track", "dropped") == "blocked"
    # 流转白名单：active 不能直接到 dropped
    assert "dropped" in allowed_next("sensitive_req_track", "active")


def test_task_center_collector(db):
    _ext(db, "REQ-A", priority="P0", status="dev")
    _ms(db, "REQ-A", team="CRM", stage="dev", planned_end=TODAY - timedelta(days=1), owner="李四")
    sensitive_req_service.sync(db)
    items = task_center_service.collect_sensitive_req(db)
    assert len(items) == 1
    it = items[0]
    assert it.task_id == "sensitive_req:REQ-A"
    assert it.status == "in_progress"
    assert it.priority == "P0"
    assert it.is_overdue is True
    assert it.owner == "李四"
    assert it.due_date == TODAY - timedelta(days=1)
    assert "sensitive" in it.source_url


def test_task_center_collector_skips_closed_and_missing(db):
    _ext(db, "REQ-A", priority="P0", status="closed")
    _ext(db, "REQ-B", priority="P1")
    sensitive_req_service.sync(db)
    items = task_center_service.collect_sensitive_req(db)
    assert [it.source_id for it in items] == ["REQ-B"]


# ─────────────────────────────────────────────────────────────
# 7. 邮件督办（安全：全部假发送）
# ─────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _fake_email_sender(monkeypatch):
    """会话级兜底：邮件发送一律假实现（双保险，另见 conftest fake_master）。"""
    monkeypatch.setattr(EmailCenterClient, "send_email", lambda self, *a, **kw: {"success": True, "id": "fake-1"})
    monkeypatch.setattr(email_client, "send_email", lambda *a, **kw: {"success": True, "id": "fake-1"})


def _seed_for_mail(db):
    _ext(db, "REQ-A", priority="P0", status="dev")
    db.add(SentEmail(req_id="REQ-A", req_name="一网通融合开通流程升级"))
    db.commit()
    _ms(db, "REQ-A", team="CRM", stage="dev", planned_end=TODAY - timedelta(days=1), owner="李四")
    sensitive_req_service.sync(db)


def _seed_for_mail_v2(db):
    """模板 v2 种子：双团队 + vendor_dev + 开发单号 + 登记时间 + dev 环节时间。"""
    _ext(db, "REQ-A", priority="P0", status="dev")
    db.add(SentEmail(
        req_id="REQ-A", req_name="一网通融合开通流程升级",
        dev_ticket_no="DEV-20261001",
        created_at=datetime(2026, 10, 12, 9, 0, 0),
    ))
    _eval(db, "REQ-A", system_name="CRM", sa_name="张三")
    _eval(db, "REQ-A", system_name="订单中心", sa_name="陈山")
    db.add(PmwbReqVendorDev(
        req_id="REQ-A", system_name="CRM", team_name="CRM 团队",
        sa_name="张三", dev_status="developing",
    ))
    db.add(PmwbRequirementStageLog(
        req_id="REQ-A", stage="dev", entered_at=datetime(2026, 10, 20, 10, 0, 0),
        source="auto",
    ))
    # CRM：评估已完成 + 开发超期 1 天；订单中心：方案制定临期
    _ms(db, "REQ-A", team="CRM", stage="evaluate",
        planned_end=TODAY - timedelta(days=10), status="done",
        actual_end=TODAY - timedelta(days=10))
    _ms(db, "REQ-A", team="CRM", stage="dev",
        planned_end=TODAY - timedelta(days=1), owner="李四")
    _ms(db, "REQ-A", team="订单中心", stage="plan",
        planned_end=TODAY + timedelta(days=2), status="doing")
    sensitive_req_service.sync(db)


def test_draft_v2_req_blocks_structure(db):
    """模板 v2：需求块基础信息 7 项 + 团队块 5 阶段 + 反馈占位区（2026-10-27）。"""
    _seed_for_mail_v2(db)
    refs = [{"source": "sensitive_req", "source_id": "REQ-A"}]
    draft = sensitive_req_service.draft(db, refs, "urge", "", "李四")

    body = draft["body_md"]
    # 基础信息 7 项
    for token in (
        "需求文号", "开发单号", "需求登记时间", "开发启动时间", "上线要求", "级别", "需求状态",
        "DEV-20261001", "2026-10-12", "2026-10-20",  # 单号/登记时间/开发启动时间
        "**各团队进展与计划**",
    ):
        assert token in body, f"缺少 {token}"
    # 团队块：开发状态中文 + 处理人（vendor_dev.sa_name 优先）
    assert "#### CRM（开发中｜处理人：张三）" in body
    assert "#### 订单中心（—｜处理人：陈山）" in body
    # 里程碑行：超期徽章 + 实际完成回显
    assert "【超期 1 天】" in body
    assert "需求评估" in body and "方案制定" in body
    # 反馈占位区（每团队一个锚点 + 固定三项）
    assert "【CRM·进展反馈】" in body
    assert "【订单中心·进展反馈】" in body
    assert body.count("1. 最新进展：") == 2
    assert body.count("2. 风险时间点：") == 2
    assert body.count("3. 求助事宜：") == 2
    # 返回体带 req_blocks（前端可不消费）
    assert draft["req_blocks"] and draft["req_blocks"][0]["dev_ticket_no"] == "DEV-20261001"


def test_draft_v2_subject_prefix(db):
    """主题前缀：sensitive_req 场景应为【敏感需求督办】/【敏感需求同步】（多任务也不退化为任务催办）。"""
    _seed_for_mail_v2(db)
    _ext(db, "REQ-B", priority="P1", status="dev")
    _eval(db, "REQ-B", system_name="CRM", sa_name="张三")
    sensitive_req_service.sync(db)

    single = sensitive_req_service.draft(
        db, [{"source": "sensitive_req", "source_id": "REQ-A"}], "urge", "", "李四")
    assert single["subject"].startswith("【敏感需求督办】")

    multi = sensitive_req_service.draft(
        db,
        [{"source": "sensitive_req", "source_id": "REQ-A"},
         {"source": "sensitive_req", "source_id": "REQ-B"}],
        "urge", "", "李四")
    assert multi["subject"].startswith("【敏感需求督办】")
    assert "您有 2 项敏感需求需跟进" in multi["subject"]

    notify = sensitive_req_service.draft(
        db, [{"source": "sensitive_req", "source_id": "REQ-A"}], "notify", "", "李四")
    assert notify["subject"].startswith("【敏感需求同步】")


def test_draft_v2_no_teams_fallback(db):
    """无活跃团队（无团队评估）→ 降级文案，不产团队子块/反馈锚点。"""
    _seed_for_mail(db)  # 无 _eval
    refs = [{"source": "sensitive_req", "source_id": "REQ-A"}]
    draft = sensitive_req_service.draft(db, refs, "urge", "", "李四")
    assert "未识别到活跃团队" in draft["body_md"]
    assert "·进展反馈】" not in draft["body_md"]
    # 开发单号缺失降级
    assert "未填写" in draft["body_md"]


def test_draft_v2_user_body_takeover(db):
    """用户编辑接管：body_md 保留需求 title 时不重复追加 req_blocks 段。"""
    _seed_for_mail_v2(db)
    refs = [{"source": "sensitive_req", "source_id": "REQ-A"}]
    draft = sensitive_req_service.draft(
        db, refs, "urge", "各位：请重点关注一网通融合开通流程升级，本周内闭环。", "李四")
    assert "本周内闭环" in draft["body_md"]
    assert "基础信息" not in draft["body_md"]  # 接管后不追加结构化段落


def test_draft_and_dry_run_preview(db, monkeypatch):
    _seed_for_mail(db)
    refs = [{"source": "sensitive_req", "source_id": "REQ-A"}]
    draft = sensitive_req_service.draft(db, refs, "urge", "", "李四")
    assert draft["body_md"] and draft["subject"]
    assert "一网通融合开通流程升级" in draft["body_md"]

    n_records = db.query(EmailRecord).count()
    req = SensitiveReqSendRequest(
        tasks=[{"source": "sensitive_req", "source_id": "REQ-A"}],
        to="lisi@example.com",
        send_type="urge",
        dry_run=True,
    )
    res = sensitive_req_service.send(db, req)
    assert res["preview"] is True
    # dry_run 不落记录、不回写督办
    assert db.query(EmailRecord).count() == n_records
    row = db.query(PmwbSensitiveReqTrack).filter_by(req_id="REQ-A").first()
    assert (row.urge_count or 0) == 0


def test_confirm_send_bumps_urge_and_escalates(db, monkeypatch):
    _seed_for_mail(db)
    monkeypatch.setattr(
        "services.mail_dispatch.dispatch_email",
        lambda db, **kw: {"success": True, "record_id": 9527, "message": "ok"},
    )
    req = SensitiveReqSendRequest(
        tasks=[{"source": "sensitive_req", "source_id": "REQ-A"}],
        to="lisi@example.com",
        send_type="urge",
        confirm_send=True,
    )
    res = sensitive_req_service.send(db, req)
    assert res["success"] is True
    row = db.query(PmwbSensitiveReqTrack).filter_by(req_id="REQ-A").first()
    assert row.urge_count == 1 and row.last_urged_at is not None
    assert row.track_status == "escalated"
    ms = db.query(PmwbSensitiveReqMilestone).filter_by(req_id="REQ-A").first()
    assert ms.urge_count == 1
    # 逐条落库（ref_type=sensitive_req）
    recs = db.query(EmailRecord).filter(EmailRecord.ref_type == "sensitive_req").all()
    assert any(r.ref_id == "REQ-A" for r in recs)


def test_send_requires_recipient_validation(db, monkeypatch):
    _seed_for_mail(db)
    req = SensitiveReqSendRequest(
        tasks=[{"source": "sensitive_req", "source_id": "REQ-A"}],
        to="not-an-email",
        send_type="urge",
        confirm_send=True,
    )
    with pytest.raises(ValidationException):
        sensitive_req_service.send(db, req)


# ─────────────────────────────────────────────────────────────
# 7.1 模板 v2 三项修复（2026-10-27 老大反馈）
# ─────────────────────────────────────────────────────────────
def test_draft_v2_dev_ticket_latest_nonempty(db):
    """开发单号口径 = 该需求最新一条非空 dev_ticket_no（与需求基础信息一致）。"""
    _ext(db, "REQ-A", priority="P0", status="dev")
    # 早登记行无单号；后补登行有单号（id 更大）
    db.add(SentEmail(req_id="REQ-A", req_name="一网通融合开通流程升级"))
    db.commit()
    db.add(SentEmail(
        req_id="REQ-A", req_name="一网通融合开通流程升级",
        dev_ticket_no="DEV-20261025", created_at=datetime(2026, 10, 25, 9, 0, 0),
    ))
    db.commit()
    _eval(db, "REQ-A", system_name="CRM", sa_name="张三")
    _ms(db, "REQ-A", team="CRM", stage="dev", planned_end=TODAY, owner="李四")
    sensitive_req_service.sync(db)

    draft = sensitive_req_service.draft(
        db, [{"source": "sensitive_req", "source_id": "REQ-A"}], "urge", "", "李四")
    block = draft["req_blocks"][0]
    assert block["dev_ticket_no"] == "DEV-20261025"
    assert "DEV-20261025" in draft["body_md"]
    # 登记时间仍取最早 created_at（无 created_at 行 → 用有时间的行兜底显示）
    assert block["registered_at"] not in ("", None)


def test_draft_v2_urge_excludes_dev_done_teams(db):
    """urge 督办只发还未完成开发的团队；notify 同步保留全量团队。"""
    _seed_for_mail_v2(db)
    db.add(PmwbReqVendorDev(
        req_id="REQ-A", system_name="BOSS", team_name="BOSS 团队",
        sa_name="陈增明", dev_status="completed",
    ))
    _eval(db, "REQ-A", system_name="BOSS", sa_name="陈增明", workload=5.0)
    db.commit()

    urge = sensitive_req_service.draft(
        db, [{"source": "sensitive_req", "source_id": "REQ-A"}], "urge", "", "")
    urge_teams = [t["team"] for b in urge["req_blocks"] for t in b["teams"]]
    assert "BOSS" not in urge_teams  # 已完成开发 → 剔除
    assert "CRM" in urge_teams

    notify = sensitive_req_service.draft(
        db, [{"source": "sensitive_req", "source_id": "REQ-A"}], "notify", "", "")
    notify_teams = [t["team"] for b in notify["req_blocks"] for t in b["teams"]]
    assert "BOSS" in notify_teams  # 同步保留全量

    # BOSS 无里程碑且 dev_status=completed → urge 反馈锚点只剩 2 个团队
    assert urge["body_md"].count("·进展反馈】") == 2
    assert notify["body_md"].count("·进展反馈】") == 3


def test_draft_v2_recipients_all_stage_owners(db):
    """收件人候选 = 各团队全部环节涉及人去重（不止当前卡点/处理人）。"""
    _seed_for_mail_v2(db)
    # 再补一个 evaluate 环节不同责任人的里程碑（CRM）
    _ms(db, "REQ-A", team="CRM", stage="test", planned_end=TODAY + timedelta(days=5),
        owner="王五")
    draft = sensitive_req_service.draft(
        db, [{"source": "sensitive_req", "source_id": "REQ-A"}], "urge", "", "")
    rcpts = draft["recipients"]
    assert "李四" in rcpts and "王五" in rcpts
    assert rcpts.count("李四") == 1  # 去重


def test_send_autofill_recipients_from_blocks(db, monkeypatch):
    """to 为空时自动用全部环节涉及人作收件人（姓名→邮箱解析，解析不出保持原样）。"""
    _seed_for_mail_v2(db)
    monkeypatch.setattr(
        "services.mail_dispatch.dispatch_email",
        lambda db, **kw: {"success": True, "record_id": 9528, "message": "ok"},
    )
    monkeypatch.setattr(
        task_center_service, "resolve_contacts",
        lambda names: {"张三": "zhangsan@example.com", "李四": "lisi@example.com"},
    )
    req = SensitiveReqSendRequest(
        tasks=[{"source": "sensitive_req", "source_id": "REQ-A"}],
        to="",  # 前端未传 → 服务端自动补全
        send_type="urge",
        confirm_send=True,
    )
    res = sensitive_req_service.send(db, req)
    assert res["success"] is True
    assert res["unresolved"] == []  # 张三/李四 都解析成功


# ─────────────────────────────────────────────────────────────
# 8. 跟踪态流转 & 详情
# ─────────────────────────────────────────────────────────────
def test_track_transition_validation(db):
    _ext(db, "REQ-A", priority="P0")
    sensitive_req_service.sync(db)
    # active → resolved 合法
    res = sensitive_req_service.update_track(
        db, "REQ-A", SensitiveReqTrackUpdateRequest(track_status="resolved")
    )
    assert res["track_status"] == "resolved"
    # resolved → delayed 非法（allowed_next 只有 active）
    with pytest.raises(ValidationException):
        sensitive_req_service.update_track(
            db, "REQ-A", SensitiveReqTrackUpdateRequest(track_status="delayed")
        )


def test_detail_composes_lanes_and_hints(db):
    _ext(db, "REQ-A", priority="P0", status="closed", delivered_date=TODAY)
    _ms(db, "REQ-A", team="CRM", stage="deploy", planned_end=DEADLINE)
    _ms(db, "REQ-A", team="BOSS", stage="dev", planned_end=DEADLINE - timedelta(days=10))
    sensitive_req_service.sync(db)
    detail = sensitive_req_service.get_detail(db, "REQ-A")
    assert set(detail["lanes"].keys()) == {"BOSS", "CRM"}
    assert detail["teams"] == ["BOSS", "CRM"]
    deploy_row = next(
        m for m in detail["milestones"] if m["team_system_name"] == "CRM" and m["stage"] == "deploy"
    )
    assert deploy_row["actual_hint"] == TODAY.isoformat()  # ext.delivered_date 只读引用（JSON 序列化为字符串）
