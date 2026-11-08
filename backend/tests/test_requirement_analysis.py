"""需求分析专题（AI总结）collect 口径单测 —— 2026-11-08 重写。

锁定口径（改这几条等于改业务定义，须老大确认）：
1. **已上线**：delivered_date（回退开发工单 go_live_date）落在区间内才计入；
   closed 但缺日期 → 进 quality 待补录，**不再进正文**（原「未填报」口径导致
   8 月老需求每期重复出现，2026-11-06 报告实证）。
2. **在途过程进展**：本周有环节/开发事件动作才进 inflight；纯编号需求名（如
   「敏捷需求（2026）第（xxx）号」）与作废需求（含「申请不开发」等）不进正文。
3. **下周计划上线**：T1 期望下周 / T1b 承诺已过（仅 dev/partial_live/live_failed）/
   T2 dev 超期 / T3 资费类，reasons 可多命中。
4. 报告为团队成效反馈：规则版同样不得出现「超期」等负面措辞。

安全：不涉邮件发送，不写 MySQL（内存 SQLite）。
"""
from datetime import date, datetime, timedelta

from constants import requirement_analysis as R
from db.models import PmwbDevTicket, PmwbReqDevEvent, PmwbRequirementExt, PmwbRequirementStageLog
from services import requirement_analysis as ra

START = date(2026, 10, 12)   # 周一
END = date(2026, 10, 18)     # 周日
NEXT_MON = date(2026, 10, 19)
NEXT_SUN = date(2026, 10, 25)


def add_req(db, req_id, status="dev", name=None, delivered=None, vrd=None,
            category=None, clarification="支持一网通业务办理，提升一线效率。"):
    db.add(PmwbRequirementExt(
        req_id=req_id, status=status, req_name=name or f"需求{req_id}",
        system_name="CRM", clarification=clarification, delivered_date=delivered,
        version_required_date=vrd, category=category,
    ))
    db.commit()


def add_ticket(db, req_id, go_live):
    db.add(PmwbDevTicket(req_id=req_id, ticket_no=f"T-{req_id}", system_name="CRM", go_live_date=go_live))
    db.commit()


def add_stage(db, req_id, stage, day, left=None):
    db.add(PmwbRequirementStageLog(
        req_id=req_id, stage=stage,
        entered_at=datetime.combine(day, datetime.min.time()) + timedelta(hours=10),
        left_at=(datetime.combine(left, datetime.min.time()) + timedelta(hours=18)) if left else None,
    ))
    db.commit()


def add_event(db, req_id, etype, day, title="启动开发"):
    db.add(PmwbReqDevEvent(
        req_id=req_id, event_type=etype,
        event_time=datetime.combine(day, datetime.min.time()) + timedelta(hours=11),
        title=title,
    ))
    db.commit()


# ── 已上线 ────────────────────────────────────────────────────────────────
def test_closed_with_date_in_period_goes_to_delivered(db):
    add_req(db, "R1", status="closed", delivered=date(2026, 10, 15))
    data = ra.collect(db, START, END)
    assert [x["req_id"] for x in data["delivered"]] == ["R1"]
    assert data["delivered"][0]["go_live"] == "2026-10-15"
    assert data["quality"] == []


def test_closed_with_date_out_of_period_excluded_everywhere(db):
    add_req(db, "R2", status="closed", delivered=date(2026, 8, 1))
    data = ra.collect(db, START, END)
    assert data["delivered"] == []
    assert data["inflight"] == []
    assert data["planned"] == []
    assert data["quality"] == []


def test_closed_without_date_goes_to_quality_not_delivered(db):
    """核心修正：无上线日期 ≠ 本周上线，进待补录而不是正文。"""
    add_req(db, "R3", status="closed")
    add_stage(db, "R3", "dev", END - timedelta(days=30))
    data = ra.collect(db, START, END)
    assert data["delivered"] == []
    assert data["planned"] == []
    assert [x["req_id"] for x in data["quality"]] == ["R3"]


def test_closed_without_date_uses_ticket_go_live(db):
    add_req(db, "R4", status="closed")
    add_ticket(db, "R4", date(2026, 10, 16))
    data = ra.collect(db, START, END)
    assert [x["req_id"] for x in data["delivered"]] == ["R4"]
    assert data["quality"] == []


def test_partial_live_with_date_counts_as_delivered(db):
    add_req(db, "R5", status="partial_live", delivered=date(2026, 10, 14))
    data = ra.collect(db, START, END)
    assert [x["req_id"] for x in data["delivered"]] == ["R5"]


# ── 下周计划三通道 ────────────────────────────────────────────────────────
def test_t1_vrd_in_next_week(db):
    add_req(db, "P1", status="dev", vrd=NEXT_MON)
    data = ra.collect(db, START, END)
    item = next(x for x in data["planned"] if x["req_id"] == "P1")
    assert "T1" in item["reasons"]


def test_t1b_vrd_passed_only_for_dev_stage(db):
    add_req(db, "P2", status="dev", vrd=date(2026, 9, 20))
    add_req(db, "P3", status="accepted", vrd=date(2026, 9, 20))
    data = ra.collect(db, START, END)
    ids = {x["req_id"] for x in data["planned"]}
    assert "P2" in ids          # 已进开发，承诺日期已过 → 纳入收口
    assert "P3" not in ids      # 仍建议/已受理 → 不纳入


def test_t2_dev_overdue(db):
    add_req(db, "P4", status="dev")
    add_stage(db, "P4", "dev", END - timedelta(days=20))
    data = ra.collect(db, START, END, overdue_days=15)
    item = next(x for x in data["planned"] if x["req_id"] == "P4")
    assert "T2" in item["reasons"]
    assert item["dev_overdue_days"] == 20


def test_t3_tariff_without_overdue(db):
    add_req(db, "P5", status="accepted", category=R.TARIFF_CATEGORY)
    add_req(db, "P6", status="accepted", clarification="新增资费：增加两档套餐")
    data = ra.collect(db, START, END)
    ids = {x["req_id"] for x in data["planned"]}
    assert {"P5", "P6"} <= ids


def test_tariff_category_not_used_when_already_t1(db):
    """已命中 T1 的资费需求不重复打 T3（reasons 只留真实依据）。"""
    add_req(db, "P7", status="dev", vrd=NEXT_SUN, category=R.TARIFF_CATEGORY)
    data = ra.collect(db, START, END)
    item = next(x for x in data["planned"] if x["req_id"] == "P7")
    assert item["reasons"] == ["T1"]


def test_paused_and_suspended_excluded(db):
    add_req(db, "X1", status="paused")
    add_req(db, "X2", status="suspended")
    data = ra.collect(db, START, END)
    assert data["delivered"] == [] and data["inflight"] == [] and data["planned"] == []


def test_dropped_requirement_excluded(db):
    add_req(db, "X3", status="dev", clarification="业务部门评估无需适配，此功能申请不开发")
    data = ra.collect(db, START, END)
    assert data["inflight"] == [] and data["planned"] == []


# ── 在途过程进展 ──────────────────────────────────────────────────────────
def test_inflight_actions_from_stage_and_event(db):
    add_req(db, "I1", status="dev")
    add_stage(db, "I1", "evaluate", START + timedelta(days=1))
    add_stage(db, "I1", "dev", START + timedelta(days=2))
    add_event(db, "I1", "dev_start", START + timedelta(days=2))
    data = ra.collect(db, START, END)
    item = next(x for x in data["inflight"] if x["req_id"] == "I1")
    assert "启动系统开发" in item["actions"]
    assert item["status_label"] == "开发中"


def test_inflight_only_when_action_in_period(db):
    """上周的动作不进本周进展（避免把旧进展当本周成果）。"""
    add_req(db, "I2", status="dev")
    add_stage(db, "I2", "dev", START - timedelta(days=10))
    data = ra.collect(db, START, END)
    assert [x["req_id"] for x in data["inflight"]] == []


def test_inflight_skips_name_only_requirement(db):
    add_req(db, "I3", status="dev", name="敏捷需求（2026）第（110500902）号")
    add_stage(db, "I3", "dev", START + timedelta(days=1))
    data = ra.collect(db, START, END)
    assert data["inflight"] == []


def test_inflight_actions_are_condensed(db):
    """多个动作合并成 1~2 段，不逐条罗列（成效反馈要简短）。"""
    add_req(db, "I4", status="dev")
    add_stage(db, "I4", "evaluate", START + timedelta(days=1))
    add_stage(db, "I4", "doc", START + timedelta(days=2))
    add_stage(db, "I4", "dev", START + timedelta(days=3))
    data = ra.collect(db, START, END)
    item = next(x for x in data["inflight"] if x["req_id"] == "I4")
    assert len(item["actions"]) <= 2
    assert "启动系统开发" in "".join(item["actions"])


# ── 提示词 / 规则版 ───────────────────────────────────────────────────────
def test_capability_strips_prefix_and_list(db):
    cap = ra._capability("电子协议系统改造： 1、配置新增加套餐资费 2、安防组网时新增应用场景必填。")
    assert cap.startswith("配置新增")
    assert len(cap) <= R.CAP_CAPABILITY


def test_build_prompt_has_three_sections(db):
    add_req(db, "Q1", status="closed", delivered=date(2026, 10, 15))
    data = ra.collect(db, START, END)
    _, user = ra.build_prompt(data, START, END)
    assert "## 一、本周已上线需求" in user
    assert "## 二、在途需求过程进展" in user
    assert "## 三、下周计划上线需求" in user
    assert "积极" in user


def test_render_rule_is_positive_and_three_sections(db):
    add_req(db, "Q2", status="dev")
    add_stage(db, "Q2", "dev", END - timedelta(days=30))
    data = ra.collect(db, START, END)
    md = ra.render_rule(data, START, END)
    for title in ("## 一、本周已上线需求", "## 二、在途需求过程进展", "## 三、下周计划上线需求"):
        assert title in md
    for bad in ("超期", "滞后", "卡点", "延误"):
        assert bad not in md
    assert "计划上线 需求Q2" in md
