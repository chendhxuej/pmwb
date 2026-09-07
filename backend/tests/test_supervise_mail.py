"""运营督办邮件链路单测（2026-09-07 改造）。

覆盖：
- 字段映射修正（category/handler/resolveDate/description，旧 type/owner/due/desc 错配回归防护）
- 纯文本工单描述换行保留（原模板通道把 \n 原样塞进 HTML 不换行）
- 留言 extra_msg 注入正文（此前后端接收后从未使用）
- 预览 = 实发（同一装配链路，HTML 逐字一致）
- 装配器模式不再调 3210 模板渲染

安全：EmailCenterClient.send_email 一律被 monkeypatch 为假实现，绝不真发。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import supervise as svc
from services.mail_dispatch import EmailCenterClient
from utils.email import email_client

TICKET = {
    "issue_no": "WO-2026-0907-001",
    "title": "一网通订单开通失败",
    "category": "订单开通",
    "issue_type": "运营问题",
    "handler": "王五",
    "due": "2026-09-10",
    "status": "处理中",
    "situation_desc": "客户反馈订单开通失败。\n已联系网络侧排查配置。",
}


def _patch(monkeypatch, capture):
    """替换真实外发与中台解析，确保测试不触网、不发信。"""
    monkeypatch.setattr(
        email_client, "resolve_contact_emails", lambda names: {n: "wangwu@example.invalid" for n in names}
    )

    def fake_send(self, **kwargs):
        capture.update(kwargs)
        return {"ok": True, "data": {}}

    monkeypatch.setattr(EmailCenterClient, "send_email", fake_send)

    def fake_render(self, template_id, data):  # pragma: no cover - 不应被调用
        capture["render_called"] = capture.get("render_called", 0) + 1
        return {"subject": "", "body": "", "bodyFormat": "html"}

    monkeypatch.setattr(EmailCenterClient, "render_template", fake_render)


def test_build_ticket_fields_mapping():
    """变量必须对齐 utils.mail_content.SCENE_FIELDS，杜绝字段空白。"""
    f = svc.build_ticket_fields(TICKET)
    assert f["no"] == "WO-2026-0907-001"
    assert f["title"] == "一网通订单开通失败"
    assert f["category"] == "订单开通"
    assert f["handler"] == "王五"
    assert f["resolveDate"] == "2026-09-10"
    assert f["status"] == "处理中"
    assert f["description"] == "客户反馈订单开通失败。\n已联系网络侧排查配置。"
    # 旧错配变量名不得再出现
    for stale in ("type", "owner", "due", "desc", "source"):
        assert stale not in f


def test_description_line_breaks_rendered(monkeypatch):
    """工单描述含换行 → 渲染为 <br>（原来挤成一行）。"""
    f = svc.build_ticket_fields(TICKET)
    out = svc.render_supervise_preview("urge", f, recipients=["王五"])
    flat = out["html"].replace("<br>\n", "<br>")
    assert "客户反馈订单开通失败。<br>已联系网络侧排查配置。" in flat


def test_extra_msg_injected_into_body(monkeypatch):
    """前端留言此前被后端丢弃，现必须出现在正文。"""
    f = svc.build_ticket_fields(TICKET)
    out = svc.render_supervise_preview("urge", f, extra_msg="请今天内反馈进展", recipients=["王五"])
    assert "补充说明" in out["html"]
    assert "请今天内反馈进展" in out["html"]


def test_greeting_and_subject(monkeypatch):
    f = svc.build_ticket_fields(TICKET)
    out = svc.render_supervise_preview("urge", f, recipients=["王五"])
    assert "王五 您好，" in out["html"]
    assert out["subject"] == "催办：一网通订单开通失败"
    # 多人 → 各位同事
    out2 = svc.render_supervise_preview("sync", f, recipients=["王五", "李四"])
    assert "各位同事，" in out2["html"]
    assert out2["subject"] == "同步：一网通订单开通失败"


def test_preview_equals_send(monkeypatch):
    """预览与发送必须逐字一致（此前预览传空 variables，工单信息全空）。"""
    capture: dict = {}
    _patch(monkeypatch, capture)

    preview = svc.render_supervise_preview(
        "urge", svc.build_ticket_fields(TICKET), extra_msg="尽快处理", recipients=["王五"]
    )
    sent = svc.supervise_ticket("urge", TICKET, ["王五"], extra_msg="尽快处理")

    assert sent["ok"] is True
    assert preview["html"] == sent["body"]
    assert capture.get("render_called", 0) == 0, "装配器模式不应再调 3210 模板渲染"
    # 发信用的正文即预览正文
    assert capture["body"] == preview["html"]


def test_action_fields_mapping():
    f = svc.build_action_fields(
        {"id": "9", "content": "补充商客专区用例", "owner": "张三", "due_date": "2026-09-12", "status": "进行中"},
        "urge",
    )
    assert f["content"] == "补充商客专区用例"
    assert f["owner"] == "张三"
    assert f["dueDate"] == "2026-09-12"
    assert f["status"] == "进行中"
    assert f["sceneLabel"] == "催办"
