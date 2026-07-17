"""插件接入端点测试（承接原 2525 本地中继，返回扁平 JSON）。"""
import pytest
from unittest.mock import patch


def test_plugin_health(client: "TestClient"):
    """健康检查返回 {status: ok}，对齐 2525 /health（插件校验 status==='ok'）。"""
    resp = client.get("/api/v1/plugins/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_plugin_contacts_empty(client: "TestClient"):
    """空 sa_info 时返回 success=true 且 contacts 为空列表。"""
    resp = client.get("/api/v1/plugins/contacts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["contacts"] == []


def test_plugin_ingest_and_cleanup(client: "TestClient", db):
    """ingest 写入 sent_emails 并返回 affectedRows/insertId。"""
    from db.models import SentEmail

    payload = {
        "reqId": "REQ-PMWB-UT",
        "reqName": "单元测试需求",
        "proposer": "UT",
        "system": "PMWB",
        "sa": "UT-SA",
    }
    resp = client.post("/api/v1/plugins/ingest", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["affectedRows"] == 1

    row = db.query(SentEmail).filter(SentEmail.req_id == "REQ-PMWB-UT").first()
    assert row is not None
    assert row.sa_name == "UT-SA"
    assert row.is_involved == 1

    # 清理
    db.delete(row)
    db.commit()


def test_plugin_contact_crud(client: "TestClient"):
    """收件人 增 -> 查重 -> 改 -> 删 全链路。"""
    # 增
    resp = client.post(
        "/api/v1/plugins/contacts",
        json={"sa_name": "UT-SA", "system_name": "PMWB", "email": "ut@example.com"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # 查重
    resp = client.get(
        "/api/v1/plugins/contacts/check",
        params={"sa_name": "UT-SA", "system_name": "PMWB"},
    )
    assert resp.json()["exists"] is True

    # 改
    resp = client.put(
        "/api/v1/plugins/contacts",
        json={
            "old_name": "UT-SA",
            "old_system": "PMWB",
            "old_email": "ut@example.com",
            "sa_name": "UT-SA2",
            "system_name": "PMWB",
            "email": "ut2@example.com",
        },
    )
    assert resp.json()["success"] is True

    # 删
    resp = client.delete(
        "/api/v1/plugins/contacts",
        params={"sa_name": "UT-SA2", "system_name": "PMWB", "email": "ut2@example.com"},
    )
    assert resp.json()["success"] is True

    # 删后查重应为 false
    resp = client.get(
        "/api/v1/plugins/contacts/check",
        params={"sa_name": "UT-SA2", "system_name": "PMWB"},
    )
    assert resp.json()["exists"] is False


def test_plugin_send_mocked(client: "TestClient"):
    """发信端点契约：返回 {success, messageId}，不实际外发，且透传 type 给邮件中心。"""
    with patch(
        "utils.email.EmailCenterClient.send_email",
        return_value={
            "messageId": "test-msg-1",
            "fromEmail": "pmwb@workbuddy",
            "accountId": "acc-1",
        },
    ) as mock_send:
        resp = client.post(
            "/api/v1/plugins/send",
            json={
                "to": "someone@example.com",
                "subject": "UT",
                "body": "hello",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["messageId"] == "test-msg-1"
        # 验证插件发信被标记为 xqemail_plugin 类型透传给统一邮件中心
        _, kwargs = mock_send.call_args
        assert kwargs.get("email_type") == "xqemail_plugin"
        assert kwargs.get("to") == ["someone@example.com"]
        assert kwargs.get("body_format") == "text"


def test_plugin_send_list_and_attachments(client: "TestClient"):
    """兼容插件 to/cc 数组/字符串混用，并透传附件。"""
    with patch(
        "utils.email.EmailCenterClient.send_email",
        return_value={
            "messageId": "test-msg-2",
            "fromEmail": "pmwb@workbuddy",
            "accountId": "acc-1",
        },
    ) as mock_send:
        resp = client.post(
            "/api/v1/plugins/send",
            json={
                "to": ["a@example.com", "b@example.com"],
                "cc": "c@example.com, d@example.com",
                "subject": "UT",
                "body": "hello",
                "bodyFormat": "html",
                "attachments": [
                    {"filename": "a.txt", "content": "base64", "contentType": "text/plain"}
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        _, kwargs = mock_send.call_args
        assert kwargs.get("to") == ["a@example.com", "b@example.com"]
        assert kwargs.get("cc") == ["c@example.com", "d@example.com"]
        assert kwargs.get("body_format") == "html"
        attachments = kwargs.get("attachments")
        assert attachments and len(attachments) == 1
        assert attachments[0]["contentBase64"] == "base64"
        assert attachments[0]["mimeType"] == "text/plain"
