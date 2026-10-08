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
            # 2026-10-08 方案A：正文为单一信息源（与前端 MeetingActionsView.buildSuperviseBody 对齐）。
            # 字段表已屏蔽，行动项明细改由正文承载。
            "body": (
                "- 行动项内容：补充商客专区用例\n"
                "- 负责人：张三\n"
                "- 截止日期：2026-09-12\n"
                "- 当前状态：进行中\n\n"
                "---\n"
                "请尽快推进并及时反馈进展，辛苦了！"
            ),
        },
        ["补充商客专区用例", "张三", "2026-09-12", "进行中"],
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
            # 2026-10-08 方案A：正文为单一信息源（与前端 TaskCenterView / RequirementView 对齐）。
            # 字段表已屏蔽；items 变量整段文本与正文不同，此前会被整段追加成「### 需求清单」→ 描述重复。
            "body": (
                "你负责的需求现在到前期评估环节了，麻烦尽快把下面两件事搞定，然后反馈给我：\n"
                "1. 需求前期评估（可行性、范围、依赖这些）；\n"
                "2. 工作量初评（大概要多少人天）和预计完成时间。\n\n"
                "需求信息：\n"
                "需求编号：REQ-2026-001\n"
                "需求名称：商客专区智能报价\n"
                "提出人：赵六\n\n"
                "收到后尽快回我评估结果哈，辛苦了！"
            ),
        },
        ["REQ-2026-001", "商客专区智能报价", "赵六"],
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
            # 2026-09-29 方案A：字段表屏蔽，正文为单一信息源（与前端 buildNoticeBody 对齐）
            "body": (
                "兹定于 2026-09-08 14:00 召开「商客专区运营周会」会议，敬请拨冗参加。\n\n"
                "## 会议信息\n\n"
                "- **时间**：2026-09-08 14:00 ~ 15:00\n"
                "- **地点/方式**：三楼会议室\n"
                "- **组织者**：陈大海\n\n"
                "请准时参加，携带本周进展材料。"
            ),
        },
        ["商客专区运营周会", "2026-09-08 14:00", "三楼会议室", "陈大海", "请准时参加"],
    ),
    "meeting_minutes": (
        {
            "meetingTitle": "商客专区运营周会",
            "meetingDate": "2026-09-08",
            "attendees": "陈大海、王五",
            "content": "本周确认智能报价方案。",
            # 真实调用方（MeetingService._build_meeting_variables）仍会传 actionItems；
            # 2026-09-30 起正文为单一信息源，装配器不再把它整段追加出来。
            "actionItems": "<ul><li>行动项B</li></ul>",
            # 2026-09-29 方案A：正文为单一信息源（与前端 buildMinutesBody 对齐）
            "body": (
                "「商客专区运营周会」已于 2026-09-08 14:00 召开，会议结论与待办事项如下，请按分工推进。\n\n"
                "## 一、会议信息\n\n"
                "- **参会人**：陈大海、王五\n\n"
                "## 二、议题与结论\n\n本周确认智能报价方案。\n\n"
                "## 三、待办事项\n\n- [ ] **王五**：行动项B（截止 2026-09-10）"
            ),
        },
        ["商客专区运营周会", "2026-09-08", "陈大海、王五", "本周确认智能报价方案", "行动项B"],
    ),
    "keywork_feedback": (
        {
            "work_no": "KW-2026-01",
            "title": "商客交付一次成功率提升",
            "assignee": "陈大海",
            "week": "2026-W37",
            # 2026-09-29 方案A：正文为单一信息源（与 routers/keywork.py 真实 body_md 对齐）
            "body": (
                "【重点工作周反馈】商客交付一次成功率提升（KW-2026-01）- 2026-W37 周\n\n"
                "您是该专题负责人，请牵头线下收集各成员本周进展。\n\n"
                "请反馈本周进展与下周计划。"
            ),
        },
        ["KW-2026-01", "商客交付一次成功率提升", "2026-W37", "请反馈本周进展"],
    ),
    # 2026-10-08 新增：主动优化建议（由 raw 场景注册进装配器；方案A 正文为单一信息源）
    "active_optimization_urge": (
        {
            "title": "商客专区批量导出优化",
            "priority": "P1",
            "status": "pending",
            "admin_name": "吴胜捷",
            "req_id": "REQ-2026-777",
            # 与前端 RequirementDeliveryView.buildActiveOptMailBody 对齐（已去掉自带「## 标题」）
            "body": (
                "| 字段 | 内容 |\n|------|------|\n"
                "| 工单标题 | 商客专区批量导出优化 |\n"
                "| 优先级 | P1 |\n"
                "| 评估状态 | 待评估 |\n"
                "| 业务管理员 | 吴胜捷 |\n"
                "| 关联需求 | REQ-2026-777 |\n\n"
                "### 现状描述\n\n导出功能缺失，只能逐单操作。\n\n"
                "### 优化建议\n\n增加批量导出能力。\n\n"
                "请尽快评估并反馈处理意见，谢谢。"
            ),
        },
        ["商客专区批量导出优化", "P1", "吴胜捷", "REQ-2026-777", "增加批量导出能力"],
    ),
    "active_optimization_sync": (
        {
            "title": "商客专区批量导出优化",
            "priority": "P1",
            "status": "adopted",
            "admin_name": "吴胜捷",
            "req_id": "REQ-2026-777",
            "body": (
                "| 字段 | 内容 |\n|------|------|\n"
                "| 工单标题 | 商客专区批量导出优化 |\n"
                "| 优先级 | P1 |\n"
                "| 评估状态 | 已采纳 |\n"
                "| 业务管理员 | 吴胜捷 |\n"
                "| 关联需求 | REQ-2026-777 |\n\n"
                "### 现状描述\n\n导出功能缺失，只能逐单操作。\n\n"
                "### 优化建议\n\n增加批量导出能力。\n\n"
                "请知悉以上优化建议的最新状态。"
            ),
        },
        ["商客专区批量导出优化", "P1", "吴胜捷", "REQ-2026-777", "增加批量导出能力"],
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


# 无字段 schema 的场景（active_optimization_*，纯正文驱动）没有可兜底的字段：
# 正文留空即空正文（前端也不提供「按字段重置」入口），故不纳入兜底断言。
SAMPLES_WITH_FIELDS = [k for k in sorted(SAMPLES) if mail_content.get_scene_fields(k)]


@pytest.mark.parametrize("scene", SAMPLES_WITH_FIELDS)
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


def test_meeting_minutes_body_wins_over_action_items():
    """会议纪要：正文已含待办事项时，装配器不得再追加 actionItems 段落。

    2026-09-30 事故：正文「三、待办事项」已列出行动项，装配器又把 actionItems
    字段整段追加成「### 行动项」，同一批内容在邮件里出现两次。
    字段表屏蔽场景（正文为单一信息源）必须做到"正文接管即不再补字段"。
    """
    body = (
        "「商客专区运营周会」已于 2026-09-08 14:00 召开，会议结论与待办事项如下，请按分工推进。\n\n"
        "## 三、待办事项\n\n- [ ] **王五**：行动项B（截止 2026-09-10）"
    )
    md = mail_content._compose_body_md(
        "meeting_minutes",
        {"meetingTitle": "商客专区运营周会", "actionItems": "<ul><li>行动项B</li></ul>"},
        body,
    )
    assert "### 行动项" not in md, "正文已接管时不应再追加「### 行动项」段落"
    assert md.count("行动项B") == 1


def test_action_dispatch_body_wins_over_actions():
    """行动项派发：正文已含派发内容时不再追加 actions 字段段落（同上）。"""
    body = (
        "**输出监控体系建设计划**\n\n"
        "- **所属会议**：商客业务生产运营策略对接会\n"
        "- **负责人**：王五\n"
        "- **截止日期**：2026-10-14"
    )
    md = mail_content._compose_body_md(
        "action_dispatch",
        {"meetingTitle": "商客业务生产运营策略对接会", "actions": "<ul><li>输出监控体系建设计划</li></ul>"},
        body,
    )
    assert "### 行动项清单" not in md
    assert md.count("输出监控体系建设计划") == 1


def test_hidden_scene_empty_body_still_renders_fields():
    """回归护栏：字段表屏蔽场景正文为空时，字段仍须兜底补齐（防信息静默丢失）。"""
    md = mail_content._compose_body_md(
        "meeting_minutes",
        {"meetingTitle": "商客专区运营周会", "actionItems": "<ul><li>行动项B</li></ul>"},
        "",
    )
    assert "行动项B" in md
    assert "商客专区运营周会" in md


# ---------------------------------------------------------------------------
# 2026-10-08 督办场景统一（方案A 扩面）：去重 / 单一称呼 / 归一化护栏
# ---------------------------------------------------------------------------
def test_requirement_reminder_body_is_source_no_items_append():
    """需求催办（A 类）：正文已含需求信息时，items 不得被追加成「### 需求清单」。

    事故：前端同时给 body 与 items（两段文本不同）→ `sval in md` 去重不命中 →
    同一段需求描述在邮件里出现两次（老大截图）。
    """
    body = (
        "需求信息：\n需求编号：REQ-1\n需求名称：商客专区智能报价\n"
        "需求描述：支持按客户画像推荐套餐。"
    )
    md = mail_content._compose_body_md(
        "requirement_reminder",
        {
            "reqId": "REQ-1",
            "reqName": "商客专区智能报价",
            "items": "需求描述：支持按客户画像推荐套餐。",
        },
        body,
    )
    assert "### 需求清单" not in md, "A 类场景正文已接管，不应再追加「### 需求清单」"
    assert md.count("支持按客户画像推荐套餐") == 1


def test_action_supervise_body_is_source_no_content_append():
    """会议行动项督办（A 类）：正文已含行动项内容，装配器不得再追加字段段落。"""
    body = (
        "- 行动项内容：补充用例\n- 负责人：张三\n"
        "- 截止日期：2026-09-12\n- 当前状态：进行中"
    )
    md = mail_content._compose_body_md(
        "action_supervise",
        {"content": "补充用例", "owner": "张三", "dueDate": "2026-09-12",
         "status": "进行中", "sceneLabel": "催办"},
        body,
    )
    assert "### 行动项内容" not in md
    assert md.count("补充用例") == 1


def test_norm_dedupe_across_whitespace():
    """归一化去重护栏：跨换行/空格的同义段落判定为重复，避免同一描述出现两次。"""
    body = "问题描述内容为订单校验规则异常导致业务员退回。"
    md = mail_content._compose_body_md(
        "supervise_urge",
        {"description": "问题描述内容为订单校验\n规则异常导致业务员退回。"},
        body,
    )
    assert md.count("订单校验") == 1, "跨换行同义段未被归一化去重"


def test_norm_dedupe_short_text_not_killed():
    """边界：短文本（<8 字符）不做归一化去重，防止「（无）」等占位被误杀。"""
    md = mail_content._compose_body_md("supervise_urge", {"description": "（无）"}, "正文其它内容")
    assert "（无）" in md


@pytest.mark.parametrize(
    "scene",
    ["requirement_reminder", "action_supervise", "active_optimization_urge", "active_optimization_sync"],
)
def test_hidden_scene_single_greeting(scene):
    """A 类场景：称呼只由装配器出，正文不得再自带称呼行（否则「王五 您好」出现两次）。"""
    fields, _ = SAMPLES[scene]
    out = mail_dispatch._render_mail(
        scene=scene,
        fields=fields,
        raw_content=fields.get("body") or "",
        recipient_name="王五",
    )
    assert out["html"].count("王五 您好，") == 1
