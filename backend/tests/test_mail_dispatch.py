"""统一邮件治理门面单测：覆盖 Markdown→内联样式 HTML、签名注入、净化、场景收口、降级。

不依赖真实邮件中心 / 数据库：通过 monkeypatch 替换 EmailCenterClient.send_email / render_template / list_templates。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import mail_dispatch
from utils import markdown_mail
from utils.attachment_compress import compress_attachments_for_mail_center


def test_markdown_to_email_html_includes_signature_and_inline_styles():
    html = markdown_mail.markdown_to_email_html("# 标题\n\n正文 **加粗**\n\n- 列表项1\n- 列表项2")
    assert "陈大海" in html  # 默认签名注入
    assert "中国移动通信集团江苏有限公司" in html
    assert 'style=' in html
    assert "<h1" in html
    # h1 标签上应当有非空的 style 属性（内联样式）
    h1_open = html.split("<h1")[1].split(">")[0]
    assert 'style=' in h1_open and 'font-size' in html
    assert "<strong" in html
    assert "<li" in html


def test_markdown_no_signature_when_disabled():
    html = markdown_mail.markdown_to_email_html("正文", inject_signature=False)
    assert "陈大海" not in html
    assert "中国移动通信集团江苏有限公司" not in html


def test_sanitize_strips_script():
    html = markdown_mail.markdown_to_email_html("<script>alert(1)</script>正文")
    assert "<script>" not in html
    assert "</script>" not in html
    # 标签被剥离后，其中文本可能保留并被转义；关键是不能执行脚本
    assert "正文" in html


def test_inject_signature_inline_escapes_html():
    sig = "<b>陈大海</b>\n中国移动"
    html = markdown_mail.markdown_to_email_html("正文", signature=sig)
    assert "<b>陈大海</b>" not in html  # 签名整体被逐行转义
    assert "&lt;b&gt;陈大海&lt;/b&gt;" in html or "陈大海" in html


def test_dispatch_meeting_html_and_signature(monkeypatch):
    """meeting_minutes 场景模板化：走 3210 模板渲染 + 统一签名注入。"""
    captured = {}
    calls = {"render": 0}

    def fake_list(self, template_type):
        return [{"id": "tpl-minutes", "type": template_type, "isDefault": True}]

    def fake_render(self, template_id, data):
        calls["render"] += 1
        v = data.get("variables", {})
        return {
            "subject": f"【会议纪要】{v.get('meetingTitle')}",
            "body": (
                '<div style="font-family:sans-serif;max-width:600px;margin:0 auto;">'
                f"<h2>{v.get('meetingTitle')}</h2>"
                f"<div>{v.get('content')}</div>"
                f"<div>{v.get('actionItems')}</div></div>"
            ),
            "bodyFormat": "html",
        }

    def fake_send(self, **kwargs):
        captured.update(kwargs)
        return {"ok": True, "data": {}}

    monkeypatch.setattr(mail_dispatch.EmailCenterClient, "list_templates", fake_list)
    monkeypatch.setattr(mail_dispatch.EmailCenterClient, "render_template", fake_render)
    monkeypatch.setattr(mail_dispatch.EmailCenterClient, "send_email", fake_send)
    res = mail_dispatch.dispatch_email(
        to=["a@b.com"], subject="测试",
        scene="meeting_minutes",
        variables={
            "meetingTitle": "需求评审会",
            "meetingDate": "2026-08-17",
            "attendees": "陈大海",
            "content": "<ul><li>项1</li></ul>",
            "actionItems": "<ul><li>行动项A</li></ul>",
            "body": "# 纪要\n- 项",
        },
    )
    assert res["success"] is True
    assert res["body_format"] == "html"
    assert captured["body_format"] == "html"
    assert captured["email_type"] == "meeting_minutes"
    assert calls["render"] == 1
    assert "需求评审会" in captured["body"]
    assert "<li>行动项A</li>" in captured["body"]
    assert "陈大海" in captured["body"]
    assert "font-family" in captured["body"]


def test_dispatch_text_body_is_wrapped_as_html(monkeypatch):
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
    assert "陈大海" in captured["body"]


def test_dispatch_failure_downgrades(monkeypatch):
    def fake_list(self, template_type):
        return [{"id": "tpl-n", "type": template_type, "isDefault": True}]

    def fake_render(self, template_id, data):
        return {"subject": "会议通知", "body": "<p>模板内容</p>", "bodyFormat": "html"}

    monkeypatch.setattr(mail_dispatch.EmailCenterClient, "list_templates", fake_list)
    monkeypatch.setattr(mail_dispatch.EmailCenterClient, "render_template", fake_render)

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


def test_scene_registration_all_bypass_migrated():
    """P0 收口：所有绕过门面的业务场景必须在注册表中有 scene。"""
    expected = {
        "meeting_notice",
        "meeting_minutes",
        "action_dispatch",
        "action_supervise",
        "task_reminder",
        "requirement_reminder",
        "work_report",
        "task_center_notify",
        "task_center_urge",
        "plugin",
        "supervise_sync",
        "supervise_urge",
    }
    assert set(mail_dispatch.SCENES.keys()) >= expected


def test_render_mail_preview_equals_send_body(monkeypatch):
    """预览与发送共用 _render_mail，正文应完全一致。"""
    captured = {}

    def fake_send(self, **kwargs):
        captured.update(kwargs)
        return {"ok": True, "data": {"messageId": "msg-123"}}

    monkeypatch.setattr(mail_dispatch.EmailCenterClient, "send_email", fake_send)
    preview = mail_dispatch._render_mail(scene="work_report", raw_content="# 周报\n- 项1")
    send = mail_dispatch.dispatch_email(
        to=["a@b.com"], subject="周报", scene="work_report", raw_content="# 周报\n- 项1"
    )
    assert preview["html"] == send["rendered_body"]
    assert "陈大海" in preview["html"]
    assert send["message_id"] == "msg-123"


def test_templated_scene_render_and_fallback(monkeypatch):
    """supervise 场景模板化：scene 直接走 3210 模板渲染；失败降级 variables.body → fallback_template。"""
    calls = {"render": 0, "send": 0}

    def fake_render(self, template_id, data):
        calls["render"] += 1
        v = data.get("variables", {})
        return {
            "subject": f"催办：{v.get('title')}",
            "body": f"<p>{v.get('title')}</p><div>{v.get('description', '')}</div>",
            "bodyFormat": "html",
        }

    def fake_list(self, template_type):
        return [{"id": "tpl-1", "type": template_type, "isDefault": True}]

    def fake_send(self, **kwargs):
        calls["send"] += 1
        return {"ok": True, "data": {}}

    monkeypatch.setattr(mail_dispatch.EmailCenterClient, "render_template", fake_render)
    monkeypatch.setattr(mail_dispatch.EmailCenterClient, "list_templates", fake_list)
    monkeypatch.setattr(mail_dispatch.EmailCenterClient, "send_email", fake_send)

    # supervise_urge 模板化：scene 直接走模板渲染（不再 raw）
    res = mail_dispatch.dispatch_email(
        to=["a@b.com"],
        scene="supervise_urge",
        variables={"no": "T-001", "title": "测试工单", "body": "请尽快处理该工单。"},
    )
    assert res["success"] is True
    assert calls["render"] == 1
    assert calls["send"] == 1
    assert "测试工单" in res["rendered_body"]
    assert "陈大海" in res["rendered_body"]  # 统一签名注入

    # template_id 直接传参时同样走模板渲染
    res2 = mail_dispatch.dispatch_email(
        to=["a@b.com"],
        scene="supervise_urge",
        template_id="tpl-1",
        variables={"no": "T-001", "title": "测试工单"},
    )
    assert res2["success"] is True
    assert calls["render"] >= 2
    assert "催办：测试工单" in res2["subject"]
    assert "测试工单" in res2["rendered_body"]
    assert "陈大海" in res2["rendered_body"]

    # 3210 渲染失败：优先用 variables.body（raw_content）降级，正文不空
    def fake_render_fail(self, template_id, data):
        raise RuntimeError("渲染服务不可用")

    monkeypatch.setattr(mail_dispatch.EmailCenterClient, "render_template", fake_render_fail)
    res3 = mail_dispatch.dispatch_email(
        to=["a@b.com"],
        scene="supervise_urge",
        variables={"no": "T-002", "title": "测试", "body": "降级测试正文"},
    )
    assert res3["success"] is True
    assert "降级测试正文" in res3["rendered_body"]
    assert "陈大海" in res3["rendered_body"]

    # 无 body 时降级用场景 fallback_template（通用 Markdown 兜底）
    res4 = mail_dispatch.dispatch_email(
        to=["a@b.com"],
        scene="supervise_urge",
        variables={"no": "T-003", "title": "测试"},
    )
    assert res4["success"] is True
    assert "催办通知" in res4["rendered_body"]  # supervise_urge.fallback_template


def test_plugin_html_passthrough(monkeypatch):
    """插件传入 HTML 时应原样净化并注入签名。"""
    captured = {}

    def fake_send(self, **kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(mail_dispatch.EmailCenterClient, "send_email", fake_send)
    from services.plugin import plugin_service

    plugin_service.send_email(
        to=["a@b.com"],
        subject="插件测试",
        body="<p>HTML 段落</p>",
        body_format="html",
    )
    assert "<p>HTML 段落</p>" in captured["body"]
    assert "陈大海" in captured["body"]
    assert captured["email_type"] == "xqemail_plugin"


def test_plugin_html_passthrough_preserves_inline_styles(monkeypatch):
    """插件传入带内联样式的 HTML 表格时，样式与表格兼容性属性应被保留，避免邮件排版错乱。"""
    captured = {}

    def fake_send(self, **kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(mail_dispatch.EmailCenterClient, "send_email", fake_send)
    from services.plugin import plugin_service

    html_body = (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
        'style="background:#fff;border:1px solid #d0d7de;border-radius:8px;">'
        '<tr><td width="90" valign="top" style="padding:10px;color:#888;width:90px;">需求编号</td>'
        '<td width="100%" style="padding:10px;color:#333;width:100%;">0700137</td></tr>'
        '</table>'
    )
    plugin_service.send_email(
        to=["a@b.com"],
        subject="插件表格测试",
        body=html_body,
        body_format="html",
    )
    body = captured["body"]
    # 关键样式必须保留
    assert 'background:#fff' in body
    assert 'border:1px solid #d0d7de' in body
    assert 'border-radius:8px' in body
    assert 'padding:10px' in body
    assert 'color:#888' in body
    assert 'color:#333' in body
    assert 'width:90px' in body
    assert 'width:100%' in body
    # 邮件客户端兼容性 HTML 属性必须保留
    assert 'cellpadding="0"' in body
    assert 'cellspacing="0"' in body
    assert 'border="0"' in body
    assert 'width="100%"' in body
    assert 'width="90"' in body
    assert 'valign="top"' in body
    assert 'role="presentation"' in body
    # 危险内容仍应被净化
    assert '<script>' not in body
    # 统一签名注入
    assert "陈大海" in body


def test_plugin_text_body_markdown_rendered(monkeypatch):
    """插件传入 text 时应按 Markdown 渲染为 HTML 并加签名。"""
    captured = {}

    def fake_send(self, **kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(mail_dispatch.EmailCenterClient, "send_email", fake_send)
    from services.plugin import plugin_service

    plugin_service.send_email(
        to=["a@b.com"],
        subject="插件测试",
        body="**加粗** 正文",
        body_format="text",
    )
    assert captured["body_format"] == "html"
    assert "<strong>加粗</strong>" in captured["body"] or "加粗" in captured["body"]
    assert "陈大海" in captured["body"]


def test_compress_falls_back_to_byte_probe_when_mime_missing():
    """根因回归：插件截图 file.type 为空时被标成 application/octet-stream，
    压缩兜底此前因 mime 判断跳过，导致大图原样转发 3210 触发 413（无附件成功、有附件就 413）。
    改为字节探测后，真实图片无论 mime 声明如何都应被压缩。
    """
    from PIL import Image, ImageDraw
    import io, base64, random

    img = Image.new("RGB", (3600, 2400), (245, 246, 248))
    d = ImageDraw.Draw(img)
    random.seed(11)
    for _ in range(700):
        x, y = random.randint(0, 3600), random.randint(0, 2400)
        w, h = random.randint(60, 500), random.randint(20, 140)
        d.rectangle([x, y, x + w, y + h], fill=(random.randint(180, 255),) * 3,
                    outline=(random.randint(80, 160),) * 3)
        d.line([x, y, x + w, y + random.randint(0, h)], fill=(random.randint(40, 120),) * 3, width=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    assert len(b64) > 70 * 1024  # 超过压缩触发阈值

    atts = [{"filename": "shot.png", "contentBase64": b64, "mimeType": "application/octet-stream"}]
    out = compress_attachments_for_mail_center(atts)
    assert out[0]["mimeType"] == "image/jpeg"  # 识别为图片并转 JPEG
    assert len(out[0]["contentBase64"]) < len(b64)  # 体积被压缩，不会原样转发
