"""运营监控工单附件自动带出：单元 + 集成测试。

覆盖：
- build_operation_attachment_block：清单生成、真实文件 base64、缺失文件、超限跳过
- supervise_ticket：自动把工单附件清单注入正文（desc/description 双写）+ 真实文件作为 MIME 附件
"""
import base64
import os
from unittest import mock

from utils.operation_attachment import build_operation_attachment_block


def _write_issue_file(upload_root, issue_id, name, content=b"hello"):
    folder = os.path.join(upload_root, str(issue_id))
    os.makedirs(folder, exist_ok=True)
    fp = os.path.join(folder, name)
    with open(fp, "wb") as f:
        f.write(content)
    return fp


def test_build_block_single_file(tmp_path, monkeypatch):
    monkeypatch.setattr("utils.operation_attachment._UPLOAD_ROOT", str(tmp_path))
    issue_id = 7
    name = "报告.xlsx"
    _write_issue_file(str(tmp_path), issue_id, name, b"abcdef" * 100)
    metas = [{"name": name, "bytes": 600, "size": "600 B"}]
    section, real = build_operation_attachment_block(issue_id, metas)
    assert "工单附件" in section
    assert "报告.xlsx" in section
    assert "/attachments/download" in section
    assert len(real) == 1
    assert real[0]["filename"] == name
    assert base64.b64decode(real[0]["contentBase64"]) == b"abcdef" * 100


def test_build_block_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr("utils.operation_attachment._UPLOAD_ROOT", str(tmp_path))
    metas = [{"name": "gone.xlsx", "size": "1 KB"}]
    section, real = build_operation_attachment_block(99, metas)
    assert "文件缺失" in section
    assert real == []


def test_build_block_over_size(tmp_path, monkeypatch):
    monkeypatch.setattr("utils.operation_attachment._UPLOAD_ROOT", str(tmp_path))
    issue_id = 8
    name = "big.zip"
    _write_issue_file(str(tmp_path), issue_id, name, b"x" * (30 * 1024 * 1024))  # 30MB > 20MB
    metas = [{"name": name, "size": "30 MB"}]
    section, real = build_operation_attachment_block(issue_id, metas, max_single_mb=20)
    assert "体积过大未随信附上" in section
    assert real == []


def test_supervise_ticket_attaches(tmp_path, monkeypatch):
    """运营督办：自动把工单附件清单注入正文 + 真实文件作为 MIME 附件。

    注：自 2026-09-07 T2 改造后，supervise_ticket 走装配器链路
    （renderer=True，fields/extra_html），不再直接通过 variables.desc/description
    拼接正文。装配器行为详见 tests/test_supervise_mail.py，
    本测试聚焦附件清单与 MIME 附件在装配器链路上是否正确带出。
    """
    monkeypatch.setattr("utils.operation_attachment._UPLOAD_ROOT", str(tmp_path))
    issue_id = 9
    name = "a.docx"
    _write_issue_file(str(tmp_path), issue_id, name, b"content")
    from services import supervise as svc
    from services.mail_dispatch import dispatch_email

    captured = {}

    def fake(**kwargs):
        # 适配 dispatch_email 新签名（关键字参数：to/subject/scene/variables/fields/extra_html/attachments/...）
        captured.update(kwargs)
        return {"success": True, "subject": "s", "rendered_body": "b"}

    ticket = {
        "issue_no": "N1", "title": "t", "issue_type": "x", "category": "c",
        "handler": "h", "status": "open", "situation_desc": "desc文本", "source": "运营",
        "issue_id": issue_id, "attachments": [{"name": name, "size": "7 B"}],
    }
    monkeypatch.setattr(svc, "dispatch_email", fake)
    res = svc.supervise_ticket("urge", ticket, ["陈大海"])
    assert res.get("ok") is True

    # 装配器链路：附件清单注入 extra_html；真实文件作为 MIME 附件
    extra = captured.get("extra_html") or ""
    assert "工单附件" in extra
    assert name in extra
    attachments = captured.get("attachments") or []
    assert len(attachments) == 1
    assert attachments[0]["filename"] == name
