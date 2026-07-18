from fastapi.testclient import TestClient

from tests.factories import MeetingFactory


def test_create_meeting(client: TestClient, db):
    payload = {
        "meeting_id": "MEET-20260713-001",
        "title": "项目周会",
        "meeting_type": "project_weekly",
        "status": "planned",
        "host": "李四",
        "attendees": [{"name": "张三", "email": "zs@example.com", "is_required": 1}],
        "actions": [{"content": "整理会议纪要", "owner": "张三"}],
    }
    response = client.post("/api/v1/meetings", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["meeting_id"] == "MEET-20260713-001"
    assert data["data"]["attendees"][0]["name"] == "张三"
    assert data["data"]["actions"][0]["content"] == "整理会议纪要"


def test_list_meetings(client: TestClient, db):
    MeetingFactory.create(db, meeting_id="MEET-001")
    MeetingFactory.create(db, meeting_id="MEET-002")
    response = client.get("/api/v1/meetings")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["total"] >= 2


def test_create_meeting_empty_optional_fields(client: TestClient, db):
    """Regression: 空字符串的 start_time / end_time / due_date 不应导致 422。"""
    payload = {
        "meeting_id": "MEET-EMPTY-TIMES",
        "title": "空时间会议",
        "meeting_type": "other",
        "status": "planned",
        "start_time": "",
        "end_time": "",
        "location": "",
        "host": "",
        "summary": "",
        "obsidian_path": "",
        "related_req_id": "",
        "related_ticket_no": "",
        "attendees": [{"name": "王五", "is_required": 1}],
        "actions": [
            {"content": "待办事项", "owner": "", "due_date": "", "status": "pending"}
        ],
    }
    response = client.post("/api/v1/meetings", json=payload)
    assert response.status_code == 200
    d = response.json()["data"]
    assert d["start_time"] is None
    assert d["end_time"] is None
    assert d["actions"][0]["due_date"] is None
    # owner/location/host 等字符串可选字段：前端规范化后发 null，后端也接受空串
    assert d["actions"][0]["owner"] in (None, "")


def test_create_meeting_with_agenda_and_action_meta(client: TestClient, db):
    """会议可携带议题（结论/分工）与带分类、模板的行动项。"""
    payload = {
        "meeting_id": "MEET-AG-001",
        "title": "需求评审会",
        "meeting_type": "requirement_review",
        "status": "planned",
        "host": "老大",
        "convener": "邵建",
        "attendee_notes": "提前发材料",
        "agendas": [
            {"seq": 1, "topic": "量子专线模型", "conclusion": "按购物车模式", "division": "邵建提供模板"},
            {"seq": 2, "topic": "接口规范", "conclusion": "会后发出"},
        ],
        "actions": [
            {
                "content": "细化接口规范",
                "owner": "王辅松",
                "category": "operation",
                "template": "厂家团队待办模板",
            }
        ],
    }
    res = client.post("/api/v1/meetings", json=payload)
    assert res.status_code == 200
    d = res.json()["data"]
    assert d["convener"] == "邵建"
    assert d["attendee_notes"] == "提前发材料"
    assert len(d["agendas"]) == 2
    assert d["agendas"][0]["topic"] == "量子专线模型"
    assert d["agendas"][0]["conclusion"] == "按购物车模式"
    assert d["agendas"][0]["division"] == "邵建提供模板"
    assert d["actions"][0]["category"] == "operation"
    assert d["actions"][0]["template"] == "厂家团队待办模板"


def test_update_meeting_agenda_replace(client: TestClient, db):
    """更新会议时，议题列表全量替换（旧议题被清除）。"""
    create = client.post(
        "/api/v1/meetings",
        json={
            "meeting_id": "MEET-UPD-001",
            "title": "迭代会",
            "agendas": [{"seq": 1, "topic": "旧议题"}],
        },
    )
    mid = create.json()["data"]["id"]
    assert len(create.json()["data"]["agendas"]) == 1

    upd = client.put(
        f"/api/v1/meetings/{mid}",
        json={"agendas": [{"seq": 1, "topic": "新议题A"}, {"seq": 2, "topic": "新议题B"}]},
    )
    assert upd.status_code == 200
    agendas = upd.json()["data"]["agendas"]
    assert len(agendas) == 2
    assert {a["topic"] for a in agendas} == {"新议题A", "新议题B"}


def test_sync_action_todo(client: TestClient, db):
    """会议行动项可同步为 PMWB 待办任务（带分类/模板，source=meeting），且幂等。"""
    create = client.post(
        "/api/v1/meetings",
        json={
            "meeting_id": "MEET-SYNC-001",
            "title": "同步测试会",
            "actions": [
                {"content": "输出方案", "owner": "张三", "category": "operation", "template": "领导交办待办模板"},
            ],
        },
    )
    d = create.json()["data"]
    mid = d["id"]
    aid = d["actions"][0]["id"]

    res = client.post(f"/api/v1/meetings/{mid}/actions/{aid}/sync-todo")
    assert res.status_code == 200
    sync = res.json()["data"]
    assert sync["created"] is True
    todo_id = sync["todo_id"]
    assert todo_id

    # 行动项已回填关联待办
    m = client.get(f"/api/v1/meetings/{mid}").json()["data"]
    assert m["actions"][0]["related_todo_id"] == todo_id

    # 待办中心可见，且带来源与分类
    todos = client.get("/api/v1/todos", params={"source": "meeting"}).json()["data"]
    assert todos["total"] >= 1
    item = next(t for t in todos["items"] if t["id"] == todo_id)
    assert item["category"] == "operation"
    assert item["related_type"] == "meeting"
    assert item["related_id"] == str(mid)

    # 幂等：再次同步不重复建待办
    res2 = client.post(f"/api/v1/meetings/{mid}/actions/{aid}/sync-todo")
    assert res2.json()["data"]["created"] is False
    assert res2.json()["data"]["todo_id"] == todo_id
