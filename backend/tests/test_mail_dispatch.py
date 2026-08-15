"""统一邮件治理门面单测：覆盖 Markdown→HTML 转换、签名注入、纯文本签名、降级。

不依赖真实邮件中心 / 数据库：通过 monkeypatch 替换 EmailCenterClient.send_email。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import mail_dispatch
from utils import markdown_mail


def test_markdown_to_email_html_includes_signature_and_styles():
    html = markdown_mail.markdown_to_email_html("# 标题\n\n正文 **加粗**\n\n- 列表项1\n- 列表项2")
    assert "pmwb-mail-body" in html
    assert "陈大海" in html  # 默认签名注入
    assert "<h1" in html
    assert "<strong>" in html
    assert "<li>" in html


def test_markdown_no_signature_when_disabled():
    html = markdown_mail.markdown_to_email_html("正文", inject_signature=False)
    assert "陈大海" not in html
    assert "中国移动通信集团江苏有限公司" not in html


def test_dispatch_html_formats_and_sends(monkeypatch):
    captured = {}

    def fake_send(self, **kwargs):
        captured.update(kwargs)
        return {"ok": True, "data": {}}

    monkeypatch.setattr(mail_dispatch.EmailCenterClient, "send_email", fake_send)
    res = mail_dispatch.dispatch_email(
        to=["a@b.com"], subject="测试", body="# 纪要\n- 项", scene="meeting_minutes"
    )
    assert res["success"] is True
    assert res["body_format"] == "html"
    assert "pmwb-mail-body" in captured["body"]
    assert "陈大海" in captured["body"]
    assert captured["body_format"] == "html"
    assert captured["email_type"] == "meeting_minutes"


def test_dispatch_text_appends_signature(monkeypatch):
    captured = {}

    def fake_send(self, **kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(mail_dispatch.EmailCenterClient, "send_email", fake_send)
    res = mail_dispatch.dispatch_email(
        to=["a@b.com"], subject="s", body="纯文本正文", body_format="text"
    )
    assert res["body_format"] == "text"
    assert "纯文本正文" in captured["body"]
    assert "陈大海" in captured["body"]  # 纯文本签名追加


def test_dispatch_failure_downgrades(monkeypatch):
    def fake_send(self, **kwargs):
        raise RuntimeError("邮件中心挂了")

    monkeypatch.setattr(mail_dispatch.EmailCenterClient, "send_email", fake_send)
    res = mail_dispatch.dispatch_email(
        to=["a@b.com"], subject="s", body="x", scene="meeting_notice"
    )
    assert res["success"] is False
    assert "邮件中心挂了" in res["message"]


def test_dispatch_raise_on_error(monkeypatch):
    def fake_send(self, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(mail_dispatch.EmailCenterClient, "send_email", fake_send)
    raised = False
    try:
        mail_dispatch.dispatch_email(
            to=["a@b.com"], subject="s", body="x", raise_on_error=True
        )
    except RuntimeError:
        raised = True
    assert raised, "raise_on_error=True 时应抛出异常"
