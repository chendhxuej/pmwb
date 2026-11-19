"""pb-1 / L1 版本计划回归（SQLite 内存库，不触碰 MySQL 运行态）。

覆盖：倒排偏移、默认回落、专属优先、改期派生重算与留痕、CRM 闸门规则、
版本序列（顺延目标）、字典校验、重复登记、登记页预览端点。
断言按项目铁律写成 (name, cond, extra) 等价的显式 assert，禁恒 PASS。
"""

from datetime import date

import pytest

from constants import paiban as C
from services import paiban_version as svc


@pytest.fixture(autouse=True)
def fake_system_dict(monkeypatch):
    """系统字典唯一源在人员中台；测试期注入内存实现，避免出网 / 脏数据。"""
    monkeypatch.setattr(
        svc, "target_system_options",
        lambda db: {"options": ["CRM", "订单中心"], "degraded": False, "master_count": 2},
    )


def _create(client, **kw):
    payload = {
        "version_no": "2026-12 统一版",
        "scope_type": "default",
        "release_date": "2026-12-20",
        "operator": "pytest",
    }
    payload.update(kw)
    return client.post("/api/v1/paiban/versions", json=payload)


def _data(resp):
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
    body = resp.json()
    assert body.get("code") == 0, f"包络异常: {body}"
    return body.get("data")


def test_meta_offsets(client, db):
    data = _data(client.get("/api/v1/paiban/meta"))
    assert [s["offset_days"] for s in data["stages"]] == [-15, -8, -3, -1], "决策 #2 倒排偏移"
    assert data["default_admit_lead_days"] == 7, "决策 #3 CRM 提前 7 自然日"
    assert "CRM" in data["system_options"], "系统字典来自唯一源"


def test_derive_deadlines_pure():
    d = C.derive_deadlines(date(2026, 12, 20))
    assert [s["deadline"] for s in d["stages"]] == [
        "2026-12-05", "2026-12-12", "2026-12-17", "2026-12-19",
    ], "由发布日派生，不逐单手填"
    assert d["freeze_date"] == "2026-12-05"
    assert C.admit_gate_at(date(2026, 12, 20), "wait_release_n_days", 7) == "2026-12-13"
    assert C.admit_gate_at(date(2026, 12, 20), "open", 0) == ""


def test_create_and_list(client, db):
    created = _data(_create(client))
    assert created["scope_type"] == "default"
    assert created["deadlines"]["stages"][0]["deadline"] == "2026-12-05"
    listed = _data(client.get("/api/v1/paiban/versions"))
    assert listed["total"] == 1, f"实际 {listed['total']}"
    assert listed["default_count"] == 1
    assert listed["items"][0]["id"] == created["id"]


def test_resolve_falls_back_to_default(client, db):
    _create(client)
    res = _data(client.get("/api/v1/paiban/resolve", params={"system": "订单中心"}))
    assert res["source"] == "default", f"实际 {res['source']}"
    assert "统一默认" in res["source_label"]
    assert res["plan"]["release_date"] == "2026-12-20"
    assert res["plan"]["scope_type"] == "default", "回落不落副本"


def test_exclusive_plan_wins(client, db):
    _create(client)
    resp = _create(client, version_no="CRM 2026-12 常规版", scope_type="system",
                   system_name="CRM", admit_mode="wait_release_n_days", admit_lead_days=7)
    assert resp.status_code == 200, resp.text[:200]
    res = _data(client.get("/api/v1/paiban/resolve", params={"system": "CRM"}))
    assert res["source"] == "exclusive", f"实际 {res['source']}"
    assert res["plan"]["admit_gate_at"] == "2026-12-13"
    other = _data(client.get("/api/v1/paiban/resolve", params={"system": "订单中心"}))
    assert other["source"] == "default", "专属计划不影响其它系统回落"


def test_crm_gate_forbids_temp_merge(client, db):
    created = _data(_create(client, version_no="CRM 2026-12 常规版", scope_type="system",
                            system_name="CRM", admit_mode="wait_release_n_days",
                            admit_lead_days=7, allow_temp_merge=1))
    assert created["allow_temp_merge"] == 0, "闸门模式禁临时合入，默认顺延"
    assert created["is_crm"] is True
    assert created["admit_gate_at"] == "2026-12-13"


def test_change_release_date_recomputes_and_logs(client, db):
    created = _data(_create(client))
    updated = _data(client.patch(f"/api/v1/paiban/versions/{created['id']}", json={
        "release_date": "2026-12-27", "operator": "pytest",
    }))
    assert updated["deadlines"]["stages"][0]["deadline"] == "2026-12-12", "改期后派生自动重算"
    assert updated["deadlines"]["freeze_date"] == "2026-12-12"
    logs = updated["change_logs"]
    hit = [r for r in logs if r["field"] == "release_date" and r["change_type"] == "update"]
    assert len(hit) == 1, f"改期留痕条数异常: {len(hit)}"
    assert hit[0]["old_value"] == "2026-12-20" and hit[0]["new_value"] == "2026-12-27"
    assert hit[0]["operator"] == "pytest"
    res = _data(client.get("/api/v1/paiban/resolve", params={"system": "订单中心"}))
    assert res["plan"]["deadlines"]["stages"][0]["deadline"] == "2026-12-12", "回落工单同步重算"


def test_admit_rule_change_logged(client, db):
    created = _data(_create(client))
    updated = _data(client.patch(f"/api/v1/paiban/versions/{created['id']}", json={
        "admit_mode": "wait_release_n_days", "admit_lead_days": 7, "operator": "pytest",
    }))
    fields = {r["field"] for r in updated["change_logs"]}
    assert {"admit_mode", "admit_lead_days", "allow_temp_merge"} <= fields, f"缺留痕: {fields}"
    assert updated["allow_temp_merge"] == 0


def test_next_plan_sequence(client, db):
    first = _data(_create(client))
    _create(client, version_no="2027-01 统一版", release_date="2027-01-20")
    detail = _data(client.get(f"/api/v1/paiban/versions/{first['id']}"))
    assert detail["next_plan"] is not None, "顺延目标版本唯一解析"
    assert detail["next_plan"]["version_no"] == "2027-01 统一版"
    assert svc.next_plan(db, db.query(svc.PmwbPbVersionPlan).filter_by(
        version_no="2027-01 统一版").first()) is None, "最后一版进待补版本计划"


def test_duplicate_and_invalid_system(client, db):
    _create(client)
    dup = _create(client)
    assert dup.status_code in (400, 409), f"重复登记未被拒: {dup.status_code}"
    bad = _create(client, version_no="X 版", scope_type="system", system_name="不存在系统")
    assert bad.status_code == 400, f"非法系统名未被拒: {bad.status_code}"


def test_missing_plan_and_preview(client, db):
    empty = _data(client.get("/api/v1/paiban/resolve", params={"system": "订单中心"}))
    assert empty["source"] == "missing" and empty["plan"] is None
    assert "待补版本计划" in empty["hint"]
    pv = _data(client.post("/api/v1/paiban/deadlines/preview", json={
        "release_date": "2026-12-20", "admit_mode": "wait_release_n_days", "admit_lead_days": 7,
    }))
    assert pv["deadlines"]["stages"][-1]["deadline"] == "2026-12-19"
    assert pv["admit_gate_at"] == "2026-12-13"


def test_system_dict_degraded_marks_unverified(client, db, monkeypatch):
    monkeypatch.setattr(svc, "target_system_options",
                        lambda dbb: {"options": [], "degraded": True, "master_count": 0})
    created = _data(_create(client, version_no="CRM 2026-12 常规版", scope_type="system",
                            system_name="CRM"))
    assert created["system_verified"] == 0, "中台不可达：标待自动补校验，不转人工判定"
