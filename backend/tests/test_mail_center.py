"""邮件中心统计概览接口测试。"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from factories import EmailRecordFactory


class TestMailCenterStats:
    """mc-opt-1: GET /mail-center/stats 统计接口验证。"""

    def test_stats_returns_all_fields(self, client: TestClient, db):
        """基础验证：返回所有统计字段，无数据时默认值为 0。"""
        response = client.get("/api/v1/mail-center/stats")
        assert response.status_code == 200
        body = response.json()
        data = body.get("data", body)
        assert "todaySent" in data
        assert "weekSent" in data
        assert "successRate" in data
        assert "accountCount" in data
        assert "contactCount" in data
        assert "templateCount" in data
        assert "pendingAlerts" in data
        # 无数据时各项应为 0
        assert data["todaySent"] == 0
        assert data["weekSent"] == 0
        assert data["successRate"] == 0.0
        assert data["pendingAlerts"] == 0

    def test_stats_counts_today_sent(self, client: TestClient, db):
        """今日发送量：应统计当天 UTC 时间的记录。"""
        now = datetime.utcnow()
        # 今日记录
        EmailRecordFactory.create(db, send_status="success", created_at=now)
        EmailRecordFactory.create(db, send_status="success", created_at=now)
        # 昨日记录（不应计入今日）
        yesterday = now - timedelta(days=1)
        EmailRecordFactory.create(db, send_status="success", created_at=yesterday)

        response = client.get("/api/v1/mail-center/stats")
        data = response.json().get("data", response.json())
        assert data["todaySent"] == 2

    def test_stats_week_sent(self, client: TestClient, db):
        """本周发送量：应统计本周一至今的记录。"""
        now = datetime.utcnow()
        # 本周记录
        EmailRecordFactory.create(db, send_status="success", created_at=now)
        # 上周记录（不应计入本周）
        last_week = now - timedelta(days=now.weekday() + 7)
        EmailRecordFactory.create(db, send_status="success", created_at=last_week)

        response = client.get("/api/v1/mail-center/stats")
        data = response.json().get("data", response.json())
        assert data["weekSent"] >= 1

    def test_stats_success_rate(self, client: TestClient, db):
        """成功率：近7天成功记录 / 总记录。"""
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        # 3 条成功
        for _ in range(3):
            EmailRecordFactory.create(db, send_status="success", created_at=seven_days_ago + timedelta(hours=1))
        # 1 条失败
        EmailRecordFactory.create(db, send_status="failed", created_at=seven_days_ago + timedelta(hours=2))

        response = client.get("/api/v1/mail-center/stats")
        data = response.json().get("data", response.json())
        assert data["successRate"] == 75.0  # 3/4 = 75%

    def test_stats_pending_alerts(self, client: TestClient, db):
        """待处理异常：近7天失败记录数。"""
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        # 2 条失败
        for _ in range(2):
            EmailRecordFactory.create(db, send_status="failed", created_at=seven_days_ago + timedelta(hours=1))
        # 1 条成功（不应计入异常）
        EmailRecordFactory.create(db, send_status="success", created_at=seven_days_ago + timedelta(hours=2))
        # 1 条 8 天前的旧失败（不应计入近7天）
        old = datetime.utcnow() - timedelta(days=8)
        EmailRecordFactory.create(db, send_status="failed", created_at=old)

        response = client.get("/api/v1/mail-center/stats")
        data = response.json().get("data", response.json())
        assert data["pendingAlerts"] == 2
