"""需求工单 1:1 单向关联 + 全状态镜像 + 提出人写回回归。"""
import pytest
from fastapi import HTTPException

from db.models import PmwbRequirementExt, PmwbRequirementLink, SentEmail
from services.requirement import requirement_service


def _seed(db, req_id: str, proposer: str = "张三"):
    db.add(SentEmail(req_id=req_id, req_name=f"需求{req_id}", proposer=proposer, origin="plugin"))
    db.commit()


def test_set_get_and_clear_link(db):
    _seed(db, "L-A")
    _seed(db, "L-B", "李四")
    link = requirement_service.set_link(db, "L-A", "L-B")
    assert link["linked_req_id"] == "L-B"
    assert link["linked_status"] == "proposed"
    assert db.query(PmwbRequirementLink).count() == 1
    assert requirement_service.get_link(db, "L-A")["linked_req_id"] == "L-B"
    assert requirement_service.get_link(db, "L-B") is None  # 单向：从工单不反查

    requirement_service.set_link(db, "L-A", None)
    assert requirement_service.get_link(db, "L-A") is None
    assert db.query(PmwbRequirementLink).count() == 0


def test_link_validation(db):
    _seed(db, "L-A")
    _seed(db, "L-B")
    _seed(db, "L-C")
    requirement_service.set_link(db, "L-A", "L-B")
    with pytest.raises(HTTPException) as e1:
        requirement_service.set_link(db, "L-A", "L-A")
    assert e1.value.status_code == 400
    with pytest.raises(HTTPException) as e2:
        requirement_service.set_link(db, "L-A", "NOT-EXIST")
    assert e2.value.status_code == 400
    with pytest.raises(HTTPException) as e3:
        requirement_service.set_link(db, "L-B", "L-A")  # 反向成环
    assert "成环" in e3.value.detail
    with pytest.raises(HTTPException) as e4:
        requirement_service.set_link(db, "L-C", "L-B")  # 目标已被占用
    assert "1:1" in e4.value.detail


def test_status_mirror_all_states_bypasses_allowed_next(db):
    _seed(db, "L-A")
    _seed(db, "L-B")
    # 从工单预置为终态 closed；主工单 proposed → paused 合法，
    # 镜像写从工单 closed → paused 必须成功（全量镜像，不受 allowed_next 限制）。
    db.add(PmwbRequirementExt(req_id="L-B", status="closed"))
    db.commit()
    requirement_service.set_link(db, "L-A", "L-B")
    requirement_service.update_ext(db, "L-A", {"status": "paused"})
    target = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == "L-B").first()
    assert target.status == "paused"

    # 镜像只一层：主工单再变，从工单跟随；从工单无下游不递归
    requirement_service.update_ext(db, "L-A", {"status": "proposed"})
    db.expire_all()
    assert db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == "L-B").first().status == "proposed"


def test_status_mirror_does_not_run_without_status_change(db):
    _seed(db, "L-A")
    _seed(db, "L-B")
    db.add(PmwbRequirementExt(req_id="L-B", status="dev"))
    db.commit()
    requirement_service.set_link(db, "L-A", "L-B")
    requirement_service.update_ext(db, "L-A", {"personal_note": "仅备注"})
    assert db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == "L-B").first().status == "dev"


def test_update_proposer_writes_back_source(db):
    _seed(db, "L-A", "手机号码")
    updated = requirement_service.update_ext(db, "L-A", {"proposer": "王五"})
    assert updated["proposer"] == "王五"
    row = db.query(SentEmail).filter(SentEmail.req_id == "L-A").first()
    assert row.proposer == "王五"


def test_api_link_routes(client, db):
    _seed(db, "L-A")
    _seed(db, "L-B")
    r = client.put("/api/v1/requirements/L-A/link", json={"linked_req_id": "L-B"})
    assert r.status_code == 200
    assert r.json()["data"]["linked_req_id"] == "L-B"
    detail = client.get("/api/v1/requirements/L-A")
    assert detail.json()["data"]["linked_requirement"]["linked_req_id"] == "L-B"
    saved = client.put("/api/v1/requirements/L-A", json={"proposer": "赵六"})
    assert saved.json()["data"]["proposer"] == "赵六"
    assert db.query(SentEmail).filter(SentEmail.req_id == "L-A").first().proposer == "赵六"


def test_delete_requirement_cleans_link(db):
    _seed(db, "L-A")
    _seed(db, "L-B")
    requirement_service.set_link(db, "L-A", "L-B")
    requirement_service.delete_requirement(db, "L-B")
    assert db.query(PmwbRequirementLink).count() == 0
