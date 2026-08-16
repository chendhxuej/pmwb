"""首页看板接口测试（含看板重构 db-2 扩展字段）。"""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from tests.factories import (
    KnowledgeFactory,
    MeetingFactory,
    OperationIssueFactory,
    RequirementExtFactory,
    TodoFactory,
)


def test_dashboard_stats(client: TestClient, db):
    """基础测试：看板返回 stats 字段。"""
    TodoFactory.create(db, status="todo")
    MeetingFactory.create(db, status="planned")
    OperationIssueFactory.create(db, status="pending")
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "stats" in data["data"]
    assert data["data"]["stats"]["todo_total"] >= 1


def test_dashboard_module_stats(client: TestClient, db):
    """db-2 扩展：module_stats 各模块返回。"""
    # 看板按「周一为起点」的本地周窗口统计本周会议；测试固定放在本周三，避免周日跑 +1 天落到下周导致 totalThisWeek=0 的边界误判
    meeting_time = datetime.now() - timedelta(days=datetime.now().weekday()) + timedelta(days=3)
    TodoFactory.create(db, status="todo")
    MeetingFactory.create(db, status="planned", start_time=meeting_time)
    OperationIssueFactory.create(db, status="pending")
    RequirementExtFactory.create(db, status="proposed")
    KnowledgeFactory.create(db)

    response = client.get("/api/v1/dashboard")
    assert response.status_code == 200
    data = response.json().get("data", response.json())

    ms = data.get("module_stats")
    assert ms is not None, "缺少 module_stats 字段"
    assert ms["requirements"]["total"] >= 1
    # 工单/邮件无测试工厂可能为0，只验证字段存在
    assert "total" in ms["tickets"]
    assert ms["issues"]["total"] >= 1
    assert ms["meetings"]["totalThisWeek"] >= 1
    assert ms["knowledge"]["total"] >= 1
    assert "todaySent" in ms["emails"]


def test_dashboard_trend_charts(client: TestClient, db):
    """db-2 扩展：trend_charts 各趋势数据。"""
    RequirementExtFactory.create(db, status="proposed")

    response = client.get("/api/v1/dashboard")
    data = response.json().get("data", response.json())

    tc = data.get("trend_charts")
    assert tc is not None, "缺少 trend_charts 字段"
    assert "requirementsTrend" in tc
    assert "issuesTrend" in tc
    assert "ticketsTrend" in tc
    assert len(tc["requirementsTrend"]) == 7


def test_dashboard_distribution_charts(client: TestClient, db):
    """db-2 扩展：distribution_charts 分布数据。"""
    RequirementExtFactory.create(db, status="proposed")
    OperationIssueFactory.create(db, status="pending", issue_type="data_abnormal")

    response = client.get("/api/v1/dashboard")
    data = response.json().get("data", response.json())

    dc = data.get("distribution_charts")
    assert dc is not None, "缺少 distribution_charts 字段"
    assert "requirementStatusDist" in dc
    assert "issueTypeDist" in dc
    assert "ticketPriorityDist" in dc


def test_dashboard_progress_items(client: TestClient, db):
    """db-2 扩展：progress_items 字段存在。"""
    response = client.get("/api/v1/dashboard")
    data = response.json().get("data", response.json())

    pi = data.get("progress_items")
    assert pi is not None, "缺少 progress_items 字段"
    assert "keyProjects" in pi
    assert isinstance(pi["keyProjects"], list)
