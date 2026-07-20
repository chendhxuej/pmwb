from db.models import PmwbRequirementEvaluation, PmwbRequirementExt, PmwbUserStory, SentEmail
from fastapi.testclient import TestClient


def _create_sent_email(db, **kwargs):
    defaults = {
        "req_id": "REQ-DLV-001",
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
        "involve_dev": "是",
    }
    defaults.update(kwargs)
    obj = SentEmail(**defaults)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def test_list_requirement_eval_aggregates(client: TestClient, db):
    """列表应返回团队评估涉及系统汇总与复核工作量汇总。"""
    _create_sent_email(db, req_id="REQ-AGG-001")
    ext = PmwbRequirementExt(req_id="REQ-AGG-001", eval_seeded=1)
    db.add(ext)
    db.commit()
    ev1 = PmwbRequirementEvaluation(req_id="REQ-AGG-001", system_name="订单中心", review_workload=3.0)
    ev2 = PmwbRequirementEvaluation(req_id="REQ-AGG-001", system_name="生产运营平台", review_workload=2.5)
    db.add_all([ev1, ev2])
    db.commit()
    response = client.get("/api/v1/requirements")
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    target = next(i for i in items if i["req_id"] == "REQ-AGG-001")
    assert target["eval_workload"] == 5.5
    assert "订单中心" in target["eval_systems"]
    assert "生产运营平台" in target["eval_systems"]


def test_generate_user_stories_persists(client: TestClient, db):
    """生成用户故事后端应持久化到 pmwb_user_story。"""
    _create_sent_email(db, req_id="REQ-STORY-001", description="功能A。功能B。")
    response = client.post(
        "/api/v1/requirements/REQ-STORY-001/delivery/generate-user-stories",
        json={"content": "功能A。功能B。"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["stories"]) > 0
    rows = db.query(PmwbUserStory).filter(PmwbUserStory.req_id == "REQ-STORY-001").all()
    assert len(rows) == len(data["stories"])


def test_save_and_list_user_stories(client: TestClient, db):
    """全量保存用户故事后应能读取。"""
    _create_sent_email(db, req_id="REQ-STORY-002")
    payload = [
        {"seq": 1, "title": "US1", "desc": "描述", "scene": "场景", "acceptance": ["验证A"], "finalized": True},
    ]
    response = client.put("/api/v1/requirements/REQ-STORY-002/delivery/stories", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["stories"]) == 1
    assert data["stories"][0]["title"] == "US1"
    get_resp = client.get("/api/v1/requirements/REQ-STORY-002/delivery/stories")
    assert get_resp.status_code == 200
    assert len(get_resp.json()["data"]["stories"]) == 1


def test_init_folder_returns_merged_folder(client: TestClient, db):
    """init-folder 返回单一需求分析说明书文件夹。"""
    _create_sent_email(db, req_id="REQ-FOLDER-001", req_name="文件夹测试")
    response = client.post("/api/v1/requirements/REQ-FOLDER-001/delivery/init-folder")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "folder" in data
    assert "需求分析说明书" in data["folder"]


def test_delete_requirement_cleans_personal_data(client: TestClient, db):
    """删除需求应移除扩展、团队评估、用户故事，保留 sent_emails。"""
    _create_sent_email(db, req_id="REQ-DEL-001")
    ext = PmwbRequirementExt(req_id="REQ-DEL-001")
    db.add(ext)
    db.commit()
    ev = PmwbRequirementEvaluation(req_id="REQ-DEL-001", system_name="CRM")
    db.add(ev)
    db.commit()
    st = PmwbUserStory(req_id="REQ-DEL-001", seq=1, title="US1")
    db.add(st)
    db.commit()
    response = client.delete("/api/v1/requirements/REQ-DEL-001")
    assert response.status_code == 200
    assert db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == "REQ-DEL-001").first() is None
    assert db.query(PmwbRequirementEvaluation).filter(PmwbRequirementEvaluation.req_id == "REQ-DEL-001").first() is None
    assert db.query(PmwbUserStory).filter(PmwbUserStory.req_id == "REQ-DEL-001").first() is None
    assert db.query(SentEmail).filter(SentEmail.req_id == "REQ-DEL-001").first() is not None
