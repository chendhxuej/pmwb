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


def test_search_user_stories_global_desc_order(client: TestClient, db):
    """全局搜索默认全量、按创建时间倒序，并带出需求名称。"""
    import time

    _create_sent_email(db, req_id="REQ-US-A", req_name="专线受理需求")
    _create_sent_email(db, req_id="REQ-US-B", req_name="短信实名需求")
    s1 = PmwbUserStory(req_id="REQ-US-A", seq=1, title="老故事", desc="较早创建")
    db.add(s1)
    db.commit()
    time.sleep(0.01)
    s2 = PmwbUserStory(req_id="REQ-US-B", seq=1, title="新故事", desc="较晚创建")
    db.add(s2)
    db.commit()

    resp = client.get("/api/v1/user-stories/search")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] >= 2
    titles = [i["title"] for i in data["items"]]
    # 倒序：新故事在老故事之前
    assert titles.index("新故事") < titles.index("老故事")
    # 带出需求名称
    a = next(i for i in data["items"] if i["req_id"] == "REQ-US-A")
    assert a["req_name"] == "专线受理需求"


def test_search_user_stories_keyword_multi_and(client: TestClient, db):
    """空格分词多词 AND，全字段模糊命中；不匹配则排除。"""
    _create_sent_email(db, req_id="REQ-US-KW", req_name="综合需求台账")
    db.add(PmwbUserStory(req_id="REQ-US-KW", seq=1, title="宽带流失预警", desc="支持专线场景", scene="", acceptance='["验证预警"]', rules='["规则一"]'))
    db.add(PmwbUserStory(req_id="REQ-US-KW", seq=2, title="短信实名", desc="无关内容"))
    db.commit()

    # 单词命中标题
    r1 = client.get("/api/v1/user-stories/search", params={"keyword": "宽带"})
    titles1 = [i["title"] for i in r1.json()["data"]["items"]]
    assert "宽带流失预警" in titles1
    assert "短信实名" not in titles1

    # 多词 AND：标题词 + 描述词，同一条命中
    r2 = client.get("/api/v1/user-stories/search", params={"keyword": "宽带 专线"})
    titles2 = [i["title"] for i in r2.json()["data"]["items"]]
    assert "宽带流失预警" in titles2

    # 多词 AND：两词不在同一条 → 排除
    r3 = client.get("/api/v1/user-stories/search", params={"keyword": "宽带 短信"})
    assert all(i["title"] != "宽带流失预警" for i in r3.json()["data"]["items"])


def test_search_user_stories_finalized_and_paging(client: TestClient, db):
    """定稿状态筛选 + 分页。"""
    _create_sent_email(db, req_id="REQ-US-PG", req_name="分页测试")
    for i in range(1, 6):
        db.add(PmwbUserStory(req_id="REQ-US-PG", seq=i, title=f"故事{i}", finalized=1 if i % 2 else 0))
    db.commit()

    # 已定稿筛选
    rf = client.get("/api/v1/user-stories/search", params={"finalized": 1})
    assert all(i["finalized"] is True for i in rf.json()["data"]["items"])

    # 分页
    rp = client.get("/api/v1/user-stories/search", params={"page": 1, "page_size": 2})
    body = rp.json()["data"]
    assert len(body["items"]) == 2
    assert body["page"] == 1 and body["page_size"] == 2


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
