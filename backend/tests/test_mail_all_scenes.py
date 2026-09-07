"""全场景邮件正文渲染自检（2026-09-07 装配器收口）。

每个有字段 schema 的场景都走 PMWB 装配器渲染，断言：
- 含称呼、含幽灵表格 90% 宽、含统一签名
- 无 Mustache 残留、无 None / 空白字段
- 字段值确实出现在正文（防「变量错配 → 字段空白」复发）
- 正文可留空（由 in_body 字段自动补齐）

安全：仅调 _render_mail，不触发任何发送。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import mail_dispatch
from utils import mail_content

TASKS_HTML = "<ul><li><strong>商客专区运营方案</strong>（进行中，截止 09-20）</li></ul>"

SAMPLES = {
    "supervise_urge": (
        {
            "no": "WO-2026-0907-001",
            "title": "一网通订单开通失败",
            "category": "订单开通",
            "handler": "王五",
            "resolveDate": "2026-09-10",
            "status": "处理中",
            "description": "客户反馈订单开通失败。\n已联系网络侧排查。",
        },
        ["WO-2026-0907-001", "订单开通", "王五", "2026-09-10", "处理中", "客户反馈订单开通失败。"],
    ),
    "supervise_sync": (
        {
            "no": "WO-2026-0907-002",
            "title": "跨省宽带数据异常",
            "category": "数据异常",
            "handler": "李四",
            "resolveDate": "2026-09-12",
            "status": "已修复",
            "description": "数据已修复，等待验证。",
        },
        ["WO-2026-0907-002", "数据异常", "李四", "已修复", "数据已修复"],
    ),
    "action_supervise": (
        {
            "content": "补充商客专区用例",
            "owner": "张三",
            "dueDate": "2026-09-12",
            "status": "进行中",
            "sceneLabel": "催办",
        },
        ["补充商客专区用例", "张三", "2026-09-12", "进行中", "催办"],
    ),
    "action_dispatch": (
        {"meetingTitle": "需求评审会", "actions": "<ul><li>行动项A</li></ul>"},
        ["需求评审会", "行动项A"],
    ),
    "task_reminder": (
        {"taskTitle": "商客交付流程优化", "assignee": "王五", "planEnd": "2026-09-20", "status": "进行中"},
        ["商客交付流程优化", "王五", "2026-09-20", "进行中"],
    ),
    "requirement_reminder": (
        {
            "reqId": "REQ-2026-001",
            "reqName": "商客专区智能报价",
            "saName": "赵六",
            "proposeTime": "2026-09-01",
            "items": "<ul><li>需求项1</li></ul>",
        },
        ["REQ-2026-001", "商客专区智能报价", "赵六", "2026-09-01", "需求项1"],
    ),
    "task_center_notify": (
        {"tasks": TASKS_HTML},
        ["商客专区运营方案"],
    ),
    "task_center_urge": (
        {"tasks": TASKS_HTML},
        ["商客专区运营方案"],
    ),
    "meeting_notice": (
        {
            "meetingTopic": "商客专区运营周会",
            "meetingTime": "2026-09-08 14:00",
            "meetingLocation": "三楼会议室",
            "host": "陈大海",
            "body": "请准时参加，携带本周进展材料。",
        },
        ["商客专区运营周会", "2026-09-08 14:00", "三楼会议室", "陈大海", "请准时参加"],
    ),
    "meeting_minutes": (
        {
            "meetingTitle": "商客专区运营周会",
            "meetingDate": "2026-09-08",
            "attendees": "陈大海、王五",
            "content": "本周确认智能报价方案。",
            "actionItems": "<ul><li>行动项B</li></ul>",
        },
        ["商客专区运营周会", "2026-09-08", "陈大海、王五", "本周确认智能报价方案", "行动项B"],
    ),
    "keywork_feedback": (
        {
            "work_no": "KW-2026-01",
            "title": "商客交付一次成功率提升",
            "assignee": "陈大海",
            "week": "2026-W37",
            "body": "请反馈本周进展与下周计划。",
        },
        ["KW-2026-01", "商客交付一次成功率提升", "2026-W37", "请反馈本周进展"],
    ),
}


@pytest.mark.parametrize("scene", sorted(SAMPLES))
def test_scene_render(scene):
    fields, expects = SAMPLES[scene]
    out = mail_dispatch._render_mail(
        scene=scene,
        fields=fields,
        raw_content=fields.get("body") or fields.get("content") or "",
        recipient_name="王五",
    )
    html = out["html"]

    # 统一结构
    assert "王五 您好，" in html, f"{scene} 缺少称呼"
    assert 'width="90%"' in html, f"{scene} 未使用幽灵表格 90% 宽度"
    assert 'align="center"' in html
    assert "陈大海" in html, f"{scene} 缺少统一签名"
    # 宽度铁律：不得再出现 600/680 固定窄宽
    assert "max-width:600px" not in html
    assert "max-width:680px" not in html
    # 模板残留与空值
    assert "{{" not in html, f"{scene} 存在 Mustache 残留"
    assert "}}" not in html
    assert "None" not in html, f"{scene} 正文出现 None"
    # 字段值确实渲染出来
    for exp in expects:
        assert exp in html, f"{scene} 字段值未渲染: {exp}"
    # 主题非空
    assert out["subject"], f"{scene} 主题为空"


@pytest.mark.parametrize("scene", sorted(SAMPLES))
def test_scene_body_empty_falls_back_to_fields(scene):
    """正文留空时应由 in_body 字段自动补齐，不能发出空邮件。"""
    fields, expects = SAMPLES[scene]
    out = mail_dispatch._render_mail(scene=scene, fields=fields, raw_content="", recipient_name="王五")
    html = out["html"]
    for exp in expects:
        assert exp in html, f"{scene} 正文留空时字段未补齐: {exp}"


def test_body_md_dedupe_inbody_field():
    """正文已含字段内容时不重复追加。"""
    html = mail_content.build_mail_body(
        scene="supervise_urge",
        fields={"no": "1", "description": "问题描述内容"},
        body_md="### 问题描述\n\n问题描述内容",
    )
    assert html.count("问题描述内容") == 1


def test_body_md_appends_missing_inbody_field():
    """正文缺失的 in_body 字段应自动追加（任务清单不能丢）。"""
    html = mail_content.build_mail_body(
        scene="task_center_urge",
        fields={"tasks": TASKS_HTML},
        body_md="各位：\n\n以下任务已到跟进节点，麻烦尽快处理。",
    )
    assert "以下任务已到跟进节点" in html
    assert "商客专区运营方案" in html
