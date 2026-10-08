import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db.models import EmailRecord, PmwbRequirementEvaluation
from services.reminder import reminder_service


def _create_email_record(db: Session, req_id: str = "REQ-REMINDER-001", email_type: str = "pmwb_reminder") -> EmailRecord:
    record = EmailRecord(
        req_id=req_id,
        req_name="测试需求",
        email_type=email_type,
        recipient="sa@example.com",
        recipient_name="测试SA",
        subject="催办：测试需求",
        content="请尽快处理",
        send_status="success",
        source="pmwb",
        sender="pmwb",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _mock_templates(monkeypatch):
    """requirement_reminder 场景模板化：mock list_templates/render_template，避免真实依赖 3210。"""
    def fake_list(self, template_type):
        return [{"id": "tpl-r", "type": template_type, "isDefault": True}]

    def fake_render(self, template_id, data):
        v = data.get("variables", {})
        return {
            "subject": f"【需求催办】{v.get('reqName')} 请尽快处理",
            "body": f"需求编码：{v.get('reqId')} 需求名称：{v.get('reqName')} 催办内容：{v.get('items')}",
            "bodyFormat": "text",
        }

    monkeypatch.setattr("services.mail_dispatch.EmailCenterClient.list_templates", fake_list)
    monkeypatch.setattr("services.mail_dispatch.EmailCenterClient.render_template", fake_render)


def test_send_reminder_success(client: TestClient, db: Session, monkeypatch):
    _mock_templates(monkeypatch)

    def fake_send(self, **kwargs):
        return {"ok": True, "data": {"messageId": "msg-123", "status": "ok"}}
    monkeypatch.setattr("services.mail_dispatch.EmailCenterClient.send_email", fake_send)
    payload = {
        "req_id": "REQ-REMINDER-001",
        "req_name": "测试需求",
        "to": "sa@example.com",
        "subject": "催办：测试需求",
        "body": "请尽快处理该需求",
        "operator": "pmwb",
    }
    response = client.post("/api/v1/reminders/send", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["success"] is True
    assert data["data"]["record_id"] > 0

    # 验证数据库记录
    record = db.query(EmailRecord).filter(EmailRecord.req_id == "REQ-REMINDER-001").first()
    assert record is not None
    assert record.send_status == "success"
    assert record.email_type == "pmwb_reminder"
    assert record.recipient == "sa@example.com"


def test_send_reminder_stores_recipient_name(client: TestClient, db: Session, monkeypatch):
    _mock_templates(monkeypatch)

    def fake_send(self, **kwargs):
        return {"ok": True, "data": {"status": "ok"}}
    monkeypatch.setattr("services.mail_dispatch.EmailCenterClient.send_email", fake_send)
    payload = {
        "req_id": "REQ-REMINDER-NAME",
        "req_name": "测试需求",
        "to": "chen@example.com,zhao@example.com",
        "recipient_name": "陈山, 赵明",
        "subject": "催办：测试需求",
        "body": "请尽快处理",
    }
    response = client.post("/api/v1/reminders/send", json=payload)
    assert response.status_code == 200
    record = db.query(EmailRecord).filter(EmailRecord.req_id == "REQ-REMINDER-NAME").first()
    assert record is not None
    assert record.recipient_name == "陈山, 赵明"
    assert record.recipient == "chen@example.com,zhao@example.com"


def test_send_reminder_with_template_data(client: TestClient, db: Session, monkeypatch):
    """T-C：前端 template_data 全量透传（2026-10-08 改为装配器口径断言）。

    requirement_reminder 自 2026-10-08 起 renderer=True —— 正文由 PMWB 装配器渲染，
    不再消费 3210 模板（故原 mock render_template 的断言已失效）。改为断言落库 content：
    - 编辑区正文为单一信息源，完整保留；
    - 装配器输出的标题带「需求催办通知」在场；
    - items 不再被追加成「### 需求清单」（A 类场景正文接管），杜绝描述重复。
    """
    monkeypatch.setattr(
        "services.mail_dispatch.EmailCenterClient.send_email",
        lambda self, **kw: {"ok": True, "data": {"status": "ok"}},
    )
    body = (
        "需求信息：\n需求编号：REQ-TDATA\n需求名称：一网通报价工具优化\n"
        "需求描述：编辑区自定义正文"
    )
    payload = {
        "req_id": "REQ-TDATA",
        "req_name": "一网通报价工具优化",
        "to": "sa@example.com",
        "subject": "催办：一网通报价工具优化",
        "body": body,
        "template_data": {
            "reqId": "REQ-TDATA",
            "reqName": "一网通报价工具优化",
            "saName": "张三, 李四",
            "proposeTime": "2026-08-10 14:30",
            "items": "该需求已到前期评估环节，请尽快完成以下事项并反馈：\n1. 需求前期评估；\n2. 工作量初评。",
            "body": body,
        },
    }
    response = client.post("/api/v1/reminders/send", json=payload)
    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert response.json()["data"]["success"] is True

    record = db.query(EmailRecord).filter(EmailRecord.req_id == "REQ-TDATA").first()
    assert record is not None
    content = record.content or ""
    assert "需求催办通知" in content, "缺少装配器标题带"
    assert "编辑区自定义正文" in content, "编辑区正文丢失"
    assert "需求清单" not in content, "items 被重复追加成「需求清单」"
    assert "需求前期评估" not in content, "items 内容被重复追加"


def test_send_reminder_body_is_content_source(client: TestClient, db: Session, monkeypatch):
    """旧调用（无 template_data）正文仍完整发出（2026-10-08 装配器口径）。

    历史语义「items 回退 body」已被「正文为单一信息源」取代：正文本身就是信息主体。
    """
    monkeypatch.setattr(
        "services.mail_dispatch.EmailCenterClient.send_email",
        lambda self, **kw: {"ok": True, "data": {"status": "ok"}},
    )
    payload = {
        "req_id": "REQ-FB",
        "req_name": "回退测试",
        "to": "sa@example.com",
        "subject": "催办：回退测试",
        "body": "旧调用纯正文：请尽快评估并反馈。",
    }
    response = client.post("/api/v1/reminders/send", json=payload)
    assert response.status_code == 200
    assert response.json()["code"] == 0

    record = db.query(EmailRecord).filter(EmailRecord.req_id == "REQ-FB").first()
    assert record is not None
    assert "旧调用纯正文" in (record.content or "")


def test_send_reminder_failure(client: TestClient, db: Session, monkeypatch):
    _mock_templates(monkeypatch)

    def fake_send(self, **kwargs):
        return {"ok": False, "error": "邮件中心不可用"}
    monkeypatch.setattr("services.mail_dispatch.EmailCenterClient.send_email", fake_send)
    payload = {
        "req_id": "REQ-REMINDER-002",
        "req_name": "测试需求失败",
        "to": "sa@example.com",
        "subject": "催办：测试需求",
        "body": "请尽快处理",
    }
    response = client.post("/api/v1/reminders/send", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["success"] is False

    record = db.query(EmailRecord).filter(EmailRecord.req_id == "REQ-REMINDER-002").first()
    assert record is not None
    assert record.send_status == "failed"
    assert "邮件中心不可用" in record.error_msg


def test_list_reminders_by_req_id(client: TestClient, db: Session):
    _create_email_record(db, req_id="REQ-REMINDER-003")
    _create_email_record(db, req_id="REQ-REMINDER-003")
    response = client.get("/api/v1/reminders/REQ-REMINDER-003")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert len(data["data"]) == 2
    assert data["data"][0]["req_id"] == "REQ-REMINDER-003"


def test_list_reminders_empty(client: TestClient, db: Session):
    response = client.get(f"/api/v1/reminders/REQ-NOT-EXIST-{uuid.uuid4().hex[:8]}")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"] == []


def _create_evaluation_for_pending(db: Session, req_id: str, sa_name: str, workload=None, review_workload=None, dev_ticket_no: str = ""):
    obj = PmwbRequirementEvaluation(
        req_id=req_id,
        req_name="待催办需求",
        proposer="张三",
        send_datetime="2026-07-01",
        system_name="测试系统",
        sa_name=sa_name,
        workload=workload,
        review_workload=review_workload,
        dev_ticket_no=dev_ticket_no,
        opinion="",
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def test_list_pending_by_sa(client: TestClient, db: Session):
    # 待催办：工作量未填且未复核 → 按 (需求+SA) 去重归集；已填工作量排除
    _create_evaluation_for_pending(db, req_id="REQ-P-1", sa_name="陈山")
    _create_evaluation_for_pending(db, req_id="REQ-P-2", sa_name="陈山")
    # 已填工作量 → 排除
    _create_evaluation_for_pending(db, req_id="REQ-P-3", sa_name="赵明", workload=5.0)
    # 工作量未填、但已建开发单 → 仍应催办（只看工作量与复核状态，不看开发单号）
    _create_evaluation_for_pending(db, req_id="REQ-P-4", sa_name="钱七", dev_ticket_no="DEV-999")
    # 已复核（复核工作量=0，评估不需要开发）→ 排除，不得催办
    _create_evaluation_for_pending(db, req_id="REQ-P-5", sa_name="孙八", workload=0.0, review_workload=0.0)
    # 已复核（复核工作量>0）→ 排除，不得催办
    _create_evaluation_for_pending(db, req_id="REQ-P-6", sa_name="李九", workload=3.0, review_workload=3.5)

    response = client.get("/api/v1/reminders/pending")
    assert response.status_code == 200
    data = response.json()["data"]
    groups = {g["sa_name"]: g for g in data}
    assert "陈山" in groups
    assert groups["陈山"]["count"] == 2
    assert "赵明" not in groups
    assert "钱七" in groups
    assert groups["钱七"]["count"] == 1
    assert "孙八" not in groups
    assert "李九" not in groups


def test_list_records(client: TestClient, db: Session):
    _create_email_record(db, req_id="REQ-R-1")
    _create_email_record(db, req_id="REQ-R-2")
    response = client.get("/api/v1/reminders/records?limit=10")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2
    assert data[0]["req_id"] in ("REQ-R-1", "REQ-R-2")


def test_mail_center_health(client: TestClient, db: Session, monkeypatch):
    from routers.mail_center import client as mail_center_client

    monkeypatch.setattr(
        mail_center_client,
        "health_check",
        lambda: {"ok": True, "status": 200, "detail": {"database": "ok", "smtp": "ok"}},
    )
    response = client.get("/api/v1/mail-center/health")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["ok"] is True
