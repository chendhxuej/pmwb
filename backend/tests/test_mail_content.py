"""邮件正文装配器单测（2026-09-07 改造）。

覆盖：纯文本换行、称呼生成、幽灵表格 90% 宽度、品牌色带、字段名/值不丢失、
装配器渲染链路（preview=send 同一函数）、变量错配回归防护。

安全：dispatch_email 一律 dry_run（不带 confirm_send），绝不真发。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import mail_dispatch
from utils import mail_content

TICKET_FIELDS = {
    "no": "WO-2026-0907-001",
    "title": "一网通订单开通失败",
    "category": "订单开通",
    "handler": "王五",
    "resolveDate": "2026-09-10",
    "status": "处理中",
    "description": "客户反馈订单开通失败。\n已联系网络侧排查配置。\n等待客户验证。",
}


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def test_text_to_html_keeps_line_breaks():
    """纯文本换行必须渲染成 <br>——这是「邮件正文不换行」的根因修复。"""
    out = mail_content.text_to_html("第一行\n第二行")
    assert "<br>" in out
    assert "第一行" in out and "第二行" in out
    # 转义防护
    assert mail_content.text_to_html("<b>x</b>") == "&lt;b&gt;x&lt;/b&gt;"


def test_render_greeting():
    assert mail_content.render_greeting("王五") == "王五 您好，"
    assert mail_content.render_greeting("王五、李四") == "各位同事，"
    assert mail_content.render_greeting("") == "各位同事，"
    assert mail_content.render_greeting(None) == "各位同事，"


def test_markdown_fragment_has_no_680_wrapper():
    """装配器自行控制宽度，markdown 片段不能再套 680px 外壳（双层窄）。"""
    frag = mail_content.markdown_fragment("### 问题描述\n\n内容")
    assert "max-width:680px" not in frag
    assert "<h3" in frag


# ---------------------------------------------------------------------------
# 主装配入口
# ---------------------------------------------------------------------------
def test_build_mail_body_structure():
    html = mail_content.build_mail_body(
        scene="supervise_urge",
        fields=TICKET_FIELDS,
        recipient_name="王五",
    )
    # 品牌色带（督办 #f53f3f）
    assert "#f53f3f" in html
    # 称呼
    assert "王五 您好，" in html
    # 主标题与引导语
    assert "催办通知" in html
    assert "以下工单需要尽快推进" in html
    # 幽灵单元格 90% 居中（禁用 max-width:Npx;margin:0 auto）
    assert 'width="90%"' in html
    assert 'align="center"' in html
    assert "max-width:600px" not in html
    assert "max-width:680px" not in html
    # 字段标签与值全部出现（回归防护：category/handler/resolveDate 曾恒空）
    for label in ("工单编号", "标题", "类型", "处理人", "计划完成日期", "当前状态"):
        assert label in html
    for val in ("WO-2026-0907-001", "一网通订单开通失败", "订单开通", "王五", "2026-09-10", "处理中"):
        assert val in html
    # 正文（description 为 in_body 字段，自动生成 Markdown 段落）
    assert "客户反馈订单开通失败。" in html
    # 无 Mustache 残留
    assert "{{" not in html


def test_build_mail_body_description_line_breaks():
    """工单描述含换行时，渲染后必须是 <br>（原模板通道会挤成一行）。"""
    html = mail_content.build_mail_body(scene="supervise_sync", fields=TICKET_FIELDS)
    # nl2br 输出形如「第一行<br>\n第二行」，比对时忽略换行
    flat = html.replace("<br>\n", "<br>").replace("<br />", "<br>")
    assert "客户反馈订单开通失败。<br>已联系网络侧排查配置。<br>等待客户验证。" in flat


def test_build_mail_body_custom_body_md_overrides():
    html = mail_content.build_mail_body(
        scene="supervise_urge",
        fields=TICKET_FIELDS,
        body_md="## 自定义正文\n\n这是用户在编辑区改的内容。",
    )
    assert "这是用户在编辑区改的内容。" in html
    assert "自定义正文" in html


def test_build_mail_body_extra_html_appended():
    html = mail_content.build_mail_body(
        scene="supervise_urge",
        fields=TICKET_FIELDS,
        extra_html='<div id="att">工单附件（1 个）</div>',
    )
    assert html.index("工单附件（1 个）") > html.index("当前状态")


# ---------------------------------------------------------------------------
# 渲染链路（preview = send）
# ---------------------------------------------------------------------------
def test_render_mail_supervise_uses_assembler():
    """supervise 场景走装配器，不再调 3210 模板渲染。"""
    calls = {"render": 0}

    def fake_render(self, template_id, data):  # pragma: no cover - 不应被调用
        calls["render"] += 1
        return {"subject": "", "body": "", "bodyFormat": "html"}

    original = mail_dispatch.EmailCenterClient.render_template
    mail_dispatch.EmailCenterClient.render_template = fake_render
    try:
        out = mail_dispatch._render_mail(
            scene="supervise_urge",
            fields=TICKET_FIELDS,
            recipient_name="王五",
        )
    finally:
        mail_dispatch.EmailCenterClient.render_template = original

    assert calls["render"] == 0, "装配器场景不应再调 3210 渲染"
    assert "王五 您好，" in out["html"]
    assert "订单开通" in out["html"]
    assert out["body_format"] == "html"


def test_dispatch_email_dry_run_renders_fields():
    """dry_run（不带 confirm_send）只落库不真发，正文必须已装配完整。"""
    sent = {"called": False}

    def fake_send(self, **kwargs):
        sent["called"] = True
        return {"ok": True, "data": {}}

    original = mail_dispatch.EmailCenterClient.send_email
    mail_dispatch.EmailCenterClient.send_email = fake_send
    try:
        res = mail_dispatch.dispatch_email(
            to=["nobody@example.invalid"],
            scene="supervise_urge",
            fields=TICKET_FIELDS,
            recipient_name="王五",
        )
    finally:
        mail_dispatch.EmailCenterClient.send_email = original

    assert sent["called"] is False, "dry_run 下绝不能真发"
    assert res.get("dry_run") is True
    body = res.get("rendered_body", "")
    assert "订单开通" in body and "2026-09-10" in body
    assert "陈大海" in body  # 统一签名注入


def test_preview_equals_send_body():
    """预览与发送必须走同一渲染函数，输出逐字一致。"""
    kwargs = dict(scene="supervise_sync", fields=TICKET_FIELDS, recipient_name="王五")
    preview = mail_dispatch._render_mail(**kwargs)["html"]

    original = mail_dispatch.EmailCenterClient.send_email
    mail_dispatch.EmailCenterClient.send_email = lambda self, **kw: {"ok": True, "data": {}}
    try:
        res = mail_dispatch.dispatch_email(to=["nobody@example.invalid"], **kwargs)
    finally:
        mail_dispatch.EmailCenterClient.send_email = original

    assert res["rendered_body"].startswith(preview)
