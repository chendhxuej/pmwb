"""一线调研工单模块测试。

背景（2026-09-10）：该模块此前在 backend/tests 下零覆盖（research 相关全仓无匹配）。
本次随「一线调研升级为独立一级模块」一并补齐基础回归网。

覆盖范围：
    - 工单创建 / 详情 / 更新 / 删除（CRUD）
    - 列表多条件筛选：地市 / 子类 / 状态 / 关键词
    - 统计口径：各状态计数与闭环率
    - 超期标记自动刷新（_refresh_overdue）
    - 状态流：置为已解决自动写入解决时间
"""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from services.research import research_issue_service
from tests.factories import ResearchIssueFactory


def test_create_research_issue(client: TestClient, db):
    payload = {
        "issue_no": "RES-20260910-001",
        "title": "泰州一线调研问题",
        "sub_type": "leader_research",
        "status": "pending",
        "city": "taizhou",
        "issue_nature": "optimization",
        "vendor_handlers": "华为,中兴",
    }
    resp = client.post("/api/v1/research/issues", json=payload)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["issue_no"] == "RES-20260910-001"
    assert data["sub_type"] == "leader_research"
    assert data["status"] == "pending"
    assert data["city"] == "taizhou"


def test_get_research_issue_not_found(client: TestClient, db):
    resp = client.get("/api/v1/research/issues/999999")
    assert resp.status_code == 404


def test_list_research_issues_filter_by_city(client: TestClient, db):
    ResearchIssueFactory.create(db, city="nanjing", title="南京调研问题")
    ResearchIssueFactory.create(db, city="taizhou", title="泰州调研问题")
    resp = client.get("/api/v1/research/issues", params={"city": "taizhou"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["city"] == "taizhou"


def test_list_research_issues_filter_by_status_and_sub_type(client: TestClient, db):
    ResearchIssueFactory.create(db, status="pending", sub_type="leader_research")
    ResearchIssueFactory.create(db, status="processing", sub_type="leader_research")
    ResearchIssueFactory.create(db, status="pending", sub_type="frontline_station")

    resp = client.get(
        "/api/v1/research/issues",
        params={"status": "pending", "sub_type": "frontline_station"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["sub_type"] == "frontline_station"


def test_list_research_issues_keyword_hits_title_and_vendor(client: TestClient, db):
    ResearchIssueFactory.create(db, title="宽带开通异常", vendor_handlers="华为")
    ResearchIssueFactory.create(db, title="计费投诉", vendor_handlers="中兴")

    resp = client.get("/api/v1/research/issues", params={"keyword": "宽带"})
    assert resp.json()["data"]["total"] == 1

    resp = client.get("/api/v1/research/issues", params={"keyword": "中兴"})
    assert resp.json()["data"]["total"] == 1

    resp = client.get("/api/v1/research/issues", params={"keyword": "不存在的关键字"})
    assert resp.json()["data"]["total"] == 0


def test_get_research_issue_stats(client: TestClient, db):
    ResearchIssueFactory.create(db, status="pending")
    ResearchIssueFactory.create(db, status="pending")
    ResearchIssueFactory.create(db, status="processing")
    ResearchIssueFactory.create(db, status="resolved")

    resp = client.get("/api/v1/research/stats")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 4
    assert data["pending"] == 2
    assert data["processing"] == 1
    assert data["resolved"] == 1
    # 闭环率 = (resolved + closed) / total
    assert data["closed_loop_rate"] == 25.0


def test_stats_closed_loop_rate_excludes_suspended(client: TestClient, db):
    ResearchIssueFactory.create(db, status="resolved")
    ResearchIssueFactory.create(db, status="closed")
    ResearchIssueFactory.create(db, status="suspended")

    data = client.get("/api/v1/research/stats").json()["data"]
    assert data["total"] == 3
    assert data["suspended"] == 1
    # 已挂起不计入闭环
    assert data["closed_loop_rate"] == round(2 * 100 / 3, 1)


def test_overdue_flag_refreshed_on_read(db):
    """feedback_deadline 已过 → 读取时自动置 is_overdue=1。"""
    obj = ResearchIssueFactory.create(
        db, feedback_deadline=date.today() - timedelta(days=1), is_overdue=0
    )
    refreshed = research_issue_service.get(db, obj.id)
    assert refreshed.is_overdue == 1


def test_overdue_flag_cleared_when_deadline_in_future(db):
    """截止日期在未来 → 历史脏标记应被纠正为 0（避免超期状态只增不减）。"""
    obj = ResearchIssueFactory.create(
        db, feedback_deadline=date.today() + timedelta(days=3), is_overdue=1
    )
    refreshed = research_issue_service.get(db, obj.id)
    assert refreshed.is_overdue == 0


def test_update_status_sets_resolve_date(client: TestClient, db):
    obj = ResearchIssueFactory.create(db, status="processing")
    resp = client.post(
        f"/api/v1/research/issues/{obj.id}/status", params={"status": "resolved"}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "resolved"
    assert data["resolve_date"] is not None


def test_update_research_issue(client: TestClient, db):
    obj = ResearchIssueFactory.create(db, title="原标题")
    resp = client.put(
        f"/api/v1/research/issues/{obj.id}", json={"title": "新标题"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "新标题"


def test_delete_research_issue(client: TestClient, db):
    obj = ResearchIssueFactory.create(db)
    resp = client.delete(f"/api/v1/research/issues/{obj.id}")
    assert resp.status_code == 200
    assert client.get(f"/api/v1/research/issues/{obj.id}").status_code == 404
