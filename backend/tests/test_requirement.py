from fastapi.testclient import TestClient

from db.models import SentEmail
from tests.factories import RequirementExtFactory


def _create_sent_email(db, **kwargs):
    defaults = {
        "req_id": "REQ-TEST-001",
        "req_name": "测试需求",
        "proposer": "张三",
        "propose_time": "2026-07-01",
        "background": "背景",
        "description": "描述",
        "clarification": "澄清",
        "system_name": "测试系统",
        "sa_name": "李四",
        "send_datetime": "2026-07-01",
        "workload": 5.0,
        "is_involved": 1,
        "dev_ticket_no": "TICKET-001",
        "involve_dev": "是",
    }
    defaults.update(kwargs)
    obj = SentEmail(**defaults)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def test_list_requirements(client: TestClient, db):
    _create_sent_email(db, req_id="REQ-001", req_name="需求1")
    _create_sent_email(db, req_id="REQ-002", req_name="需求2")
    RequirementExtFactory.create(db, req_id="REQ-001", status="accepted")
    response = client.get("/api/v1/requirements")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["total"] >= 2


def test_get_requirement_detail(client: TestClient, db):
    _create_sent_email(db, req_id="REQ-DETAIL-001", req_name="详情需求")
    RequirementExtFactory.create(db, req_id="REQ-DETAIL-001", priority="P0", status="dev")
    response = client.get("/api/v1/requirements/REQ-DETAIL-001")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["req_id"] == "REQ-DETAIL-001"
    assert data["data"]["ext"]["priority"] == "P0"


def test_update_requirement_ext(client: TestClient, db):
    _create_sent_email(db, req_id="REQ-UPDATE-001")
    RequirementExtFactory.create(db, req_id="REQ-UPDATE-001", status="proposed")
    response = client.put(
        "/api/v1/requirements/REQ-UPDATE-001",
        json={"status": "accepted", "priority": "P1", "tags": "标签1,标签2"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["ext"]["status"] == "accepted"
    assert data["data"]["ext"]["priority"] == "P1"
    assert data["data"]["ext"]["tags"] == "标签1,标签2"


def test_get_requirement_stats(client: TestClient, db):
    _create_sent_email(db, req_id="REQ-STAT-001")
    _create_sent_email(db, req_id="REQ-STAT-002")
    RequirementExtFactory.create(db, req_id="REQ-STAT-001", status="accepted")
    response = client.get("/api/v1/requirements/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["total"] >= 2
    assert data["data"]["accepted"] >= 1


def test_stats_dedup_by_req_id(client: TestClient, db):
    """同一需求文号多条团队评估，需求总数只计1个。"""
    _create_sent_email(db, req_id="REQ-DEDUP-001", sa_name="陈山", system_name="订单中心")
    _create_sent_email(db, req_id="REQ-DEDUP-001", sa_name="戴晓飞", system_name="生产运营平台")
    _create_sent_email(db, req_id="REQ-DEDUP-001", sa_name="郑文东", system_name="CRM")
    response = client.get("/api/v1/requirements/stats")
    assert response.status_code == 200
    assert response.json()["data"]["total"] == 1


def test_list_eval_count(client: TestClient, db):
    """列表返回每个需求的团队评估数量。"""
    _create_sent_email(db, req_id="REQ-EC-001", sa_name="陈山", system_name="订单中心")
    _create_sent_email(db, req_id="REQ-EC-001", sa_name="戴晓飞", system_name="生产运营平台")
    response = client.get("/api/v1/requirements")
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    target = next(i for i in items if i["req_id"] == "REQ-EC-001")
    assert target["eval_count"] == 2


def test_get_evaluations(client: TestClient, db):
    """获取需求下所有团队评估记录（一个团队一条）。"""
    _create_sent_email(db, req_id="REQ-EVAL-001", sa_name="陈山", system_name="订单中心")
    _create_sent_email(db, req_id="REQ-EVAL-001", sa_name="郑文东", system_name="CRM")
    response = client.get("/api/v1/requirements/REQ-EVAL-001/evaluations")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2
    sas = {row["sa_name"] for row in data}
    assert sas == {"陈山", "郑文东"}
    assert "opinion" in data[0]
    assert "proposer" in data[0]  # 催办正文需要提出人上下文
    assert "system_name" in data[0]


def test_update_evaluation(client: TestClient, db):
    """更新团队评估工作量与评估意见，写入评估表且可回读。"""
    _create_sent_email(db, req_id="REQ-UE-001", sa_name="陈山", system_name="订单中心", workload=None)
    # 首次访问会从邮件自动播种，拿到评估记录自身 id
    resp0 = client.get("/api/v1/requirements/REQ-UE-001/evaluations")
    eval_id = resp0.json()["data"][0]["id"]
    response = client.put(
        f"/api/v1/requirements/REQ-UE-001/evaluations/{eval_id}",
        json={"workload": 8.5, "review_workload": 9.0, "opinion": "需评审后确认", "dev_ticket_no": "DEV-2026-001"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["workload"] == 8.5
    assert data["review_workload"] == 9.0
    assert data["opinion"] == "需评审后确认"
    assert data["dev_ticket_no"] == "DEV-2026-001"

    # 回读确认持久化
    resp2 = client.get("/api/v1/requirements/REQ-UE-001/evaluations")
    row = next(r for r in resp2.json()["data"] if r["id"] == eval_id)
    assert row["workload"] == 8.5
    assert row["review_workload"] == 9.0
    assert row["opinion"] == "需评审后确认"
    assert row["dev_ticket_no"] == "DEV-2026-001"


def test_update_evaluation_not_found(client: TestClient, db):
    """更新不存在的评估记录返回 data=None。"""
    response = client.put(
        "/api/v1/requirements/REQ-X/evaluations/999999",
        json={"workload": 1.0},
    )
    assert response.status_code == 200
    assert response.json()["data"] is None


def test_create_and_delete_evaluation(client: TestClient, db):
    """手动新增一条团队评估记录，可出现在列表；删除后不再出现（不会复活）。"""
    _create_sent_email(db, req_id="REQ-CAD-001", req_name="增删测试")
    create_resp = client.post(
        "/api/v1/requirements/REQ-CAD-001/evaluations",
        json={"sa_name": "王五", "system_name": "计费中心", "workload": 3.0, "review_workload": 3.5, "opinion": "ok", "dev_ticket_no": "T-1"},
    )
    assert create_resp.status_code == 200
    new_ev = create_resp.json()["data"]
    assert new_ev["sa_name"] == "王五"
    assert new_ev["review_workload"] == 3.5

    list_resp = client.get("/api/v1/requirements/REQ-CAD-001/evaluations")
    rows = list_resp.json()["data"]
    assert any(r["id"] == new_ev["id"] and r["review_workload"] == 3.5 for r in rows)

    del_resp = client.delete(f"/api/v1/requirements/REQ-CAD-001/evaluations/{new_ev['id']}")
    assert del_resp.status_code == 200
    assert del_resp.json()["data"]["deleted"] is True

    list_resp2 = client.get("/api/v1/requirements/REQ-CAD-001/evaluations")
    assert all(r["id"] != new_ev["id"] for r in list_resp2.json()["data"])


def test_delete_seeded_record_not_resurrect(client: TestClient, db):
    """删除由邮件播种出的评估记录后，重新读取不应再自动播种复活。"""
    _create_sent_email(db, req_id="REQ-DSR-001", sa_name="陈山", system_name="订单中心")
    resp0 = client.get("/api/v1/requirements/REQ-DSR-001/evaluations")
    eval_id = resp0.json()["data"][0]["id"]

    del_resp = client.delete(f"/api/v1/requirements/REQ-DSR-001/evaluations/{eval_id}")
    assert del_resp.status_code == 200

    resp1 = client.get("/api/v1/requirements/REQ-DSR-001/evaluations")
    assert resp1.json()["data"] == []
