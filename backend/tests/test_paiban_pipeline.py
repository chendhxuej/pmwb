"""pb-2 ~ pb-9 回归（SQLite 内存库；不触碰 MySQL、不发真邮件、不读写源表）。

断言写成显式 assert + extra 说明，禁恒 PASS；覆盖方案 10 章 A~J 组关键口径：
候选/纳入、团队双层、状态机/回退、准入/硬门禁、自动顺延、手工例外、
风险合并、督办冷却、反馈四通道采纳/回滚、概览口径。
"""

from datetime import date, timedelta

import pytest

from constants import paiban as C
from db.models import (
    PmwbOperationIssue, PmwbPbRisk, PmwbPbSuperviseBatch, PmwbPbTrack,
    PmwbPbTrackTeam, PmwbRequirementExt, SentEmail,
)
from services import paiban_candidate as CS
from services import paiban_feedback as FB
from services import paiban_overview as OV
from services import paiban_risk as RS
from services import paiban_supervise as SUP
from services import paiban_team as TEAM
from services import paiban_track as TS
from services import paiban_version as VS


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    monkeypatch.setattr(VS, "target_system_options",
                        lambda db: {"options": ["CRM", "订单中心"], "degraded": False})
    monkeypatch.setattr(TEAM, "active_team_systems", lambda db, no: [])
    monkeypatch.setattr(SUP, "resolve_recipients",
                        lambda sub: (["sa@example.com"], {"status": "ok"}))


def _plan(db, no="2026-12 统一版", release="2026-12-20", **kw):
    data = {"version_no": no, "scope_type": "default", "release_date": date.fromisoformat(release),
            "status": "confirmed", "version_type": "regular", "admit_mode": "open",
            "admit_lead_days": 0, "allow_temp_merge": 1, "operator": "pytest"}
    data.update(kw)
    return VS.create_plan(db, data)


def _req(db, no="REQ-1", status="dev", system="订单中心", owner="张三",
         expected="2026-12-10", delivered=None):
    ext = PmwbRequirementExt(req_id=no, status=status, priority="P1", req_name=f"需求{no}",
                             system_name=system, sa_name=owner,
                             version_required_date=date.fromisoformat(expected) if expected else None,
                             delivered_date=date.fromisoformat(delivered) if delivered else None)
    db.add(ext)
    db.add(SentEmail(req_id=no, req_name=f"需求{no}", system_name=system, sa_name=owner,
                     dev_ticket_no=f"DEV-{no}"))
    db.flush()


def _bug(db, no="BUG-1", status="processing", system="订单中心",
         expected="2026-12-10", category="bug", priority="P0"):
    db.add(PmwbOperationIssue(issue_no=no, title=f"工单{no}", category=category,
                              issue_type="bug" if category == "bug" else "temp_task",
                              status=status, related_system=system, handler="李四",
                              impact_level=priority, go_live_date=date.fromisoformat(expected)))
    db.flush()


def _track(db, no="REQ-1", tt="req"):
    return CS.include_once(db, tt, no, operator="pytest")


def _set_stage(db, t, stage, reason=""):
    sub = db.query(PmwbPbTrackTeam).filter_by(track_id=t["id"]).first()
    return TEAM.set_team_stage(db, sub.id, stage, reason=reason, operator="pytest",
                               done=(stage == "wait_release"))


# ── A 候选池与纳入 ───────────────────────────────────────────────
def test_a1_candidate_rules(db):
    _req(db)
    _req(db, "REQ-2", status="closed")
    _req(db, "REQ-3", expected="", system="")
    _bug(db)
    _bug(db, "BUG-2", category="task")
    got = CS.scan(db)
    reasons = {x["ticket_no"]: x["reason"] for x in got["excluded"]}
    assert any(x["ticket_no"] == "REQ-1" and x["can_include"] for x in got["items"]), got["summary"]
    assert reasons.get("REQ-2") == "closed", reasons
    assert reasons.get("REQ-3") == "no_system", reasons
    assert reasons.get("BUG-2") == "excluded_type", reasons


def test_a1b_candidate_multi_mail_no_dup(db):
    """一个需求有多封邮件时候选池只出一条（outerjoin 一对多曾重复 4 次）。"""
    _req(db, "REQ-1")
    for i in range(3):
        db.add(SentEmail(req_id="REQ-1", req_name="需求REQ-1 副本", system_name="订单中心"))
    db.flush()
    got = CS.scan(db)
    hits = [x for x in got["items"] if x["ticket_no"] == "REQ-1"]
    assert len(hits) == 1, f"REQ-1 被重复列为 {len(hits)} 条: {got['summary']}"


def test_a2_include_idempotent(db):
    _req(db)
    a = _track(db)
    b = _track(db)
    assert a["created"] and b["idempotent"] and a["id"] == b["id"], (a, b)
    assert db.query(PmwbPbTrack).count() == 1


def test_a3_source_missing_tombstone(db):
    _req(db)
    _track(db)
    db.query(PmwbRequirementExt).delete()
    db.query(SentEmail).delete()
    db.flush()
    out = CS.sync(db, operator="pytest")
    assert out["missing"] == ["REQ-1"], out
    assert db.query(PmwbPbTrack).first().active == 0


def test_a4_remove_requires_reason(db):
    _req(db)
    t = _track(db)
    with pytest.raises(Exception):
        CS.remove(db, t["id"], reason="", operator="pytest")
    CS.remove(db, t["id"], reason="重复需求", operator="pytest")
    assert db.query(PmwbPbTrack).first().active == 0


# ── B 团队双层口径 ───────────────────────────────────────────────
def test_b1_team_dedup_and_matrix(db):
    _plan(db)
    _req(db)
    t = _track(db)
    subs = TEAM.sync_teams(db, db.query(PmwbPbTrack).first())
    TEAM.sync_teams(db, db.query(PmwbPbTrack).first())
    assert len(subs) == 1 and db.query(PmwbPbTrackTeam).count() == 1
    m = TEAM.matrix(db, plan_id=1)
    assert m["main_row_count"] == 1 and m["team_row_count"] == 1, m
    assert "不可加总" in m["scope_note"]


# ── C 状态机 / 回退 ──────────────────────────────────────────────
def test_c1_forward_and_rollback_reason(db):
    _plan(db)
    _req(db)
    t = _track(db)
    _set_stage(db, t, "dev")
    assert db.query(PmwbPbTrack).first().stage == "dev"
    with pytest.raises(Exception):
        _set_stage(db, t, "plan_confirm", reason="")
    _set_stage(db, t, "plan_confirm", reason="方案重新评审")
    risks = db.query(PmwbPbRisk).filter_by(risk_type="stage_rollback").all()
    assert len(risks) == 1 and risks[0].affect_release == 1, "回退自动生成硬门禁风险"


def test_c2_main_stage_is_slowest_team(db):
    _plan(db)
    _req(db)
    t = _track(db)
    db.add(PmwbPbTrackTeam(track_id=t["id"], team_name="第二团队", stage="plan_confirm"))
    db.flush()
    _set_stage(db, t, "test")
    assert db.query(PmwbPbTrack).first().stage == "plan_confirm", "主行取最慢子行"


# ── D 准入与上线硬门禁 ───────────────────────────────────────────
def test_d1_simulate_gate(db):
    sim = TS.simulate_admission(date(2026, 12, 20), 7, date(2026, 12, 13))
    assert sim["status"] == "admitted", sim
    late = TS.simulate_admission(date(2026, 12, 20), 7, date(2026, 12, 14))
    assert late["status"] == "not_admitted", late


def test_d2_live_blocked_by_risk(db):
    _plan(db)
    _req(db)
    t = _track(db)
    _set_stage(db, t, "wait_release")
    RS.create(db, t["id"], {"risk_type": "dev_delay", "description": "开发延期",
                             "affect_release": 1})
    with pytest.raises(Exception) as exc:
        TS.set_result(db, t["id"], {"result": "live", "operator": "pytest"})
    assert "禁止登记已上线" in str(exc.value), str(exc.value)


def test_d3_live_ok_after_risk_resolved(db):
    _plan(db)
    _req(db)
    t = _track(db)
    _set_stage(db, t, "wait_release")
    r = RS.create(db, t["id"], {"risk_type": "dev_delay", "description": "开发延期",
                                 "affect_release": 1})
    RS.resolve(db, r["id"], resolution="已消除", operator="pytest")
    out = TS.set_result(db, t["id"], {"result": "live", "operator": "pytest"})
    assert out["result"] == "live" and out["planned"] is True, out


# ── E 自动顺延 ───────────────────────────────────────────────────
def test_e1_failed_auto_defers_to_next(db):
    _plan(db, "V1", "2026-12-20")
    _plan(db, "V2", "2026-12-27")
    _req(db)
    t = _track(db)
    _set_stage(db, t, "wait_release")
    out = TS.set_result(db, t["id"], {"result": "failed", "reason": "发布失败",
                                       "operator": "pytest"})
    row = db.query(PmwbPbTrack).first()
    assert out["defer_count"] == 1 and row.defer_count == 1, out
    assert row.current_plan_id == 2 and row.stage == "test", (row.current_plan_id, row.stage)
    assert row.result == "" and row.active == 1, "主行唯一、不关闭"
    assert len(__import__("json").loads(row.plan_chain)) == 1


def test_e2_no_next_plan_goes_missing(db):
    _plan(db)
    _req(db)
    t = _track(db)
    out = TS.set_result(db, t["id"], {"result": "not_scheduled", "reason": "未排进",
                                       "operator": "pytest"})
    row = db.query(PmwbPbTrack).first()
    assert out["missing_plan"] and row.current_plan_id is None and row.active == 1, out


def test_e3_focus_and_abnormal(db):
    _plan(db, "V1", "2026-12-20")
    _plan(db, "V2", "2026-12-27")
    _plan(db, "V3", "2027-01-03")
    _plan(db, "V4", "2027-01-10")
    _req(db)
    t = _track(db)
    for _ in range(3):
        TS.set_result(db, t["id"], {"result": "not_scheduled", "reason": "未排进",
                                     "operator": "pytest"})
    row = db.query(PmwbPbTrack).first()
    assert row.defer_count == 3 and row.focus_flag == 1 and row.abnormal_flag == 1


# ── F 手工例外 ───────────────────────────────────────────────────
def test_f1_exception_requires_reason_and_idempotent(db):
    _plan(db)
    _req(db)
    db.query(PmwbRequirementExt).first().version_required_date = date(2026, 12, 5)
    t = _track(db)
    with pytest.raises(Exception):
        TS.manual_handle(db, t["id"], {"action": "allow", "operator": "pytest"})
    out = TS.manual_handle(db, t["id"], {"action": "allow", "operator": "pytest",
                                          "reason": "production_fix"})
    row = db.query(PmwbPbTrack).first()
    assert row.admit_status == "exception" and row.exception_flag == 1, out
    again = TS.manual_handle(db, t["id"], {"action": "allow", "operator": "pytest",
                                            "reason": "production_fix"})
    assert again["idempotent"] is True


def test_f2_revoke_returns_to_default_defer(db):
    _plan(db, "V1", "2026-12-20")
    _plan(db, "V2", "2026-12-27")
    _req(db)
    db.query(PmwbRequirementExt).first().version_required_date = date(2026, 12, 5)
    t = _track(db)
    TS.manual_handle(db, t["id"], {"action": "allow", "operator": "pytest",
                                    "reason": "production_fix"})
    out = TS.manual_handle(db, t["id"], {"action": "revoke", "operator": "pytest"})
    row = db.query(PmwbPbTrack).first()
    assert out["deferred"] and row.exception_flag == 0 and row.current_plan_id == 2, out


# ── G 风险合并 ───────────────────────────────────────────────────
def test_g1_risk_merge_not_duplicate(db):
    _plan(db)
    _req(db)
    t = _track(db)
    a = RS.create(db, t["id"], {"risk_type": "dev_delay", "description": "第一次"})
    b = RS.create(db, t["id"], {"risk_type": "dev_delay", "description": "第二次"})
    assert a["id"] == b["id"] and b["merge_count"] == 1, (a, b)
    assert "第一次" in b["description"] and "第二次" in b["description"]


# ── H 督办 ───────────────────────────────────────────────────────
def test_h1_supervise_preview_and_dry_run(db):
    _plan(db)
    _req(db)
    t = _track(db)
    RS.create(db, t["id"], {"risk_type": "dev_delay", "description": "开发延期",
                             "affect_release": 1})
    prev = SUP.build_preview(db, plan_id=1)
    assert prev["groups"] and prev["groups"][0]["included_count"] >= 1, prev
    out = SUP.send(db, {"plan_id": 1, "dry_run": True, "operator": "pytest"})
    assert out["dry_run"] and out["total_batches"] >= 1, out
    b = db.query(PmwbPbSuperviseBatch).first()
    assert b.dry_run == 1 and b.confirm_send == 0


def test_h2_true_send_requires_confirm(db):
    _plan(db)
    with pytest.raises(Exception):
        SUP.send(db, {"plan_id": 1, "dry_run": False, "confirm_send": False})


def test_h3_cooldown_after_real_send(db):
    _plan(db)
    _req(db)
    t = _track(db)
    from db.models import PmwbPbSuperviseItem
    from services import paiban_common as K
    db.add(PmwbPbSuperviseBatch(batch_no="PB-test-1", team_name="订单中心", ticket_type="req",
                                plan_id=1, dry_run=0, confirm_send=1, created_at=K.now_cn()))
    db.flush()
    b = db.query(PmwbPbSuperviseBatch).first()
    db.add(PmwbPbSuperviseItem(batch_id=b.id, batch_no=b.batch_no, track_id=t["id"], team_id=1,
                               ticket_no="REQ-1", receipt_code="PB-TESTCODE1",
                               send_status="sent", created_at=K.now_cn()))
    db.commit()
    assert SUP.cooldown_left_hours(db, t["id"], 1) > 0


# ── I 反馈同步 ───────────────────────────────────────────────────
def test_i1_structured_auto_adopt(db):
    _plan(db)
    _req(db)
    t = _track(db)
    out = FB.submit(db, {"channel": "inline", "track_id": t["id"], "stage": "dev",
                         "progress": "已联调", "risk": "环境未就绪", "promise_date": "2026-12-15",
                         "affect_release": 1, "operator": "pytest"})
    assert out["adopt_status"] == "auto" and out["adopted"] is True, out
    assert db.query(PmwbPbTrack).first().stage == "dev"
    assert db.query(PmwbPbRisk).count() == 1


def test_i2_free_text_pending_no_state_change(db):
    _plan(db)
    _req(db)
    t = _track(db)
    before = db.query(PmwbPbTrack).first().stage
    out = FB.submit(db, {"channel": "inline", "track_id": t["id"],
                         "raw_text": "我们这边已经进入测试中，风险是环境还没好"})
    assert out["adopt_status"] == "pending" and out.get("adopted") is not True, out
    assert db.query(PmwbPbTrack).first().stage == before, "自由文本不改任何状态"
    assert db.query(PmwbPbRisk).count() == 0


def test_i3_rollback_restores(db):
    _plan(db)
    _req(db)
    t = _track(db)
    out = FB.submit(db, {"channel": "inline", "track_id": t["id"], "stage": "test",
                         "progress": "完成开发", "risk": "测试环境待准备",
                         "promise_date": "2026-12-15", "operator": "pytest"})
    rb = FB.rollback(db, out["id"], operator="pytest")
    assert rb["rolled_back"] and rb["restored"]["stage"] == "plan_confirm", rb
    assert db.query(PmwbPbTrack).first().stage == "plan_confirm"


def test_i4_rollback_stage_without_reason_stays_pending(db):
    _plan(db)
    _req(db)
    t = _track(db)
    out = FB.submit(db, {"channel": "inline", "track_id": t["id"], "stage": "plan_confirm",
                         "progress": "退回方案", "risk": "", "promise_date": "2026-12-15"})
    assert out["adopt_status"] == "pending", out


# ── J 概览口径 ───────────────────────────────────────────────────
def test_j1_overview_excludes_exception_from_numerator(db):
    _plan(db)
    _req(db, "REQ-1")
    _req(db, "REQ-2", owner="王五")
    t1 = CS.include_once(db, "req", "REQ-1", operator="pytest")
    CS.include_once(db, "req", "REQ-2", operator="pytest")
    for t in (t1, {"id": 2}):
        _set_stage(db, t, "wait_release")
    TS.manual_handle(db, t1["id"], {"action": "allow", "operator": "pytest",
                                     "reason": "production_fix"})
    TS.set_result(db, t1["id"], {"result": "live", "operator": "pytest"})
    TS.set_result(db, 2, {"result": "live", "operator": "pytest"})
    ov = OV.overview(db, 1)
    assert ov["rates"]["decided_count"] == 2, ov["rates"]
    assert ov["rates"]["achieved_count"] == 2
    assert ov["rates"]["planned_rate"] == 0.5 and ov["rates"]["raw_rate"] == 1.0, ov["rates"]
    assert "不可加总" in ov["scope_note"]
