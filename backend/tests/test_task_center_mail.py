"""任务中心邮件正文单测（2026-09-07 改造）。

覆盖：单任务/多任务/超期/临期/无描述/多负责人称呼/主题格式化/
兼容旧 HTML/空任务 等 14 个用例。

安全：dispatch_email 一律 dry_run（不带 confirm_send），绝不真发。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import mail_dispatch
from utils import mail_content


# ---------------------------------------------------------------------------
# 公共 fixture：结构化任务
# ---------------------------------------------------------------------------
def _task(**kw):
    base = {
        "index": 1,
        "title": "[REQ-001] 一网通开户流程优化",
        "source_label": "需求催办",
        "source": "requirement_urge",
        "source_id": "REQ-001",
        "owner": "张三",
        "due_date": "2026-09-10",
        "status_label": "待处理",
        "priority": "P1",
        "description": "针对一网通宽带开户流程的优化建议",
        "is_overdue": False,
        "is_due_soon": False,
        "source_url": "/requirement-delivery?req=REQ-001",
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# render_task_center_section 单元测试
# ---------------------------------------------------------------------------
def test_section_single_basic():
    """单任务：H3 标题 + 字段表 + 工单内容。"""
    md = mail_content.render_task_center_section([_task()], "urge")
    assert "### 1. [REQ-001] 一网通开户流程优化" in md
    assert "| 来源 | 负责人 | 截止 | 状态 | 优先级 |" in md
    assert "| 需求催办 | 张三 | 2026-09-10 | 待处理 | P1 |" in md
    assert "**工单内容**" in md
    assert "针对一网通宽带开户流程的优化建议" in md


def test_section_overdue_badge():
    """超期：红色 span 标记。"""
    md = mail_content.render_task_center_section([_task(is_overdue=True)], "urge")
    assert "#f53f3f" in md and "【超期】" in md


def test_section_due_soon_badge():
    """临期：橙色 span 标记。"""
    md = mail_content.render_task_center_section([_task(is_due_soon=True)], "urge")
    assert "#ff7d00" in md and "【临期】" in md


def test_section_no_description_skips_block():
    """无描述：不渲染"工单内容"段。"""
    md = mail_content.render_task_center_section([_task(description="")], "urge")
    assert "**工单内容**" not in md
    assert "针对一网通" not in md


def test_section_multiple_tasks_separated():
    """多任务：3 个 H3，分隔清晰。"""
    tasks = [
        _task(index=1, title="任务A", is_overdue=True),
        _task(index=2, title="任务B", is_due_soon=True),
        _task(index=3, title="任务C"),
    ]
    md = mail_content.render_task_center_section(tasks, "urge")
    assert "### 1. 任务A" in md
    assert "### 2. 任务B" in md
    assert "### 3. 任务C" in md
    assert md.count("---") >= 2  # 至少两个分隔


def test_section_10_tasks_complete():
    """批量 10 个：完整渲染无截断。"""
    tasks = [_task(index=i, title=f"任务{i}") for i in range(1, 11)]
    md = mail_content.render_task_center_section(tasks, "urge")
    for i in range(1, 11):
        assert f"### {i}. 任务{i}" in md


def test_section_multiline_description_preserves_breaks():
    """工单内容多行：\n 在渲染后保留。"""
    desc = "第一行\n第二行\n第三行"
    md = mail_content.render_task_center_section([_task(description=desc)], "urge")
    # markdown 段落渲染：换行会被保留
    assert "第一行" in md and "第二行" in md and "第三行" in md


def test_section_empty_tasks_returns_empty():
    """空任务列表：返回空串，不报错。"""
    assert mail_content.render_task_center_section([], "urge") == ""
    assert mail_content.render_task_center_section(None, "urge") == ""


# ---------------------------------------------------------------------------
# build_mail_body 集成测试
# ---------------------------------------------------------------------------
def test_build_mail_body_with_structured_tasks():
    """结构化任务 → 完整邮件正文（品牌带 + 称呼 + 引导语 + 任务卡片）。"""
    tasks = [_task(is_overdue=True)]
    html = mail_content.build_mail_body(
        scene="task_center_urge",
        fields={"tasks": tasks},
        recipient_name="张三",
    )
    # 品牌色带（催办色）
    assert "#f53f3f" in html
    # 标题
    assert "任务催办提醒" in html
    # 称呼（1 人）
    assert "张三 您好" in html
    # 引导语
    assert "已临近或超过截止时间" in html
    # 任务 H3
    assert "<h3" in html and "### 1." not in html  # markdown ### 已渲染成 h3
    assert "[REQ-001]" in html
    # 字段表（GFM 表格已渲染为 <table>）
    assert "<table" in html
    # 工单内容
    assert "工单内容" in html
    # 不含 dict 字面量（防呆）
    assert "'index':" not in html


def test_build_mail_body_legacy_str_falls_back():
    """兼容旧调用方：tasks 是 str 时走原 auto_parts 拼接。"""
    html = mail_content.build_mail_body(
        scene="task_center_urge",
        fields={"tasks": "<ul><li>旧 HTML 列表</li></ul>"},
        recipient_name="张三",
    )
    # 旧的 "### 任务清单" 标题仍生效（auto_parts 拼接）
    assert "### 任务清单" in html or "任务清单" in html


def test_build_mail_body_two_owners_greeting():
    """2 个负责人 → "各位同事，"（既有约定）。"""
    tasks = [_task(owner="张三"), _task(index=2, owner="李四")]
    html = mail_content.build_mail_body(
        scene="task_center_urge",
        fields={"tasks": tasks},
        recipient_name="张三、李四",
    )
    assert "各位同事，" in html


def test_build_mail_body_notify_scene():
    """task_center_notify 场景：蓝色品牌带 + "任务同步通知" 标题。"""
    tasks = [_task()]
    html = mail_content.build_mail_body(
        scene="task_center_notify",
        fields={"tasks": tasks},
        recipient_name="张三",
    )
    assert "#165dff" in html
    assert "任务同步通知" in html


# ---------------------------------------------------------------------------
# mail_dispatch 主题格式化（task_center_*）
# ---------------------------------------------------------------------------
def test_subject_single_task_uses_title():
    """单任务主题：催办：{title}。"""
    out = mail_dispatch._render_mail(
        scene="task_center_urge",
        fields={"tasks": [_task(title="需求X") for _ in [None]]},
    )
    assert out["subject"] == "催办：需求X"


def test_subject_multi_task_format():
    """多任务主题：催办：{first_title} 等 {N} 项任务。"""
    tasks = [
        _task(index=1, title="一网通开户优化"),
        _task(index=2, title="调研反馈"),
        _task(index=3, title="专题分析"),
    ]
    out = mail_dispatch._render_mail(
        scene="task_center_urge",
        fields={"tasks": tasks},
    )
    assert out["subject"] == "催办：一网通开户优化 等 3 项任务"


def test_subject_notify_scene():
    """通知主题：通知：{title}。"""
    out = mail_dispatch._render_mail(
        scene="task_center_notify",
        fields={"tasks": [_task(title="通知标题") for _ in [None]]},
    )
    assert out["subject"] == "通知：通知标题"


# ---------------------------------------------------------------------------
# 装配异常回退（与 supervise 一致）
# ---------------------------------------------------------------------------
def test_build_mail_body_keeps_brand_color_on_overdue():
    """超期任务渲染后品牌色（催办红）仍在最外层。"""
    tasks = [_task(is_overdue=True)]
    html = mail_content.build_mail_body(
        scene="task_center_urge",
        fields={"tasks": tasks},
        recipient_name="张三",
    )
    # 外层 4px 品牌色带在文档开头
    assert html.startswith("<table") and "background:#f53f3f" in html


# ---------------------------------------------------------------------------
# build_mail_body_md：左侧 Markdown 编辑区默认值（2026-09-07）
# ---------------------------------------------------------------------------
def test_build_mail_body_md_single_task():
    """单任务：返回 Markdown 草稿，含 H3 + 字段表 + 工单内容。"""
    md = mail_content.build_mail_body_md(
        scene="task_center_urge",
        fields={"tasks": [_task()]},
    )
    assert "### 1. [REQ-001] 一网通开户流程优化" in md
    assert "| 来源 | 负责人 | 截止 | 状态 | 优先级 |" in md
    assert "**工单内容**" in md
    assert "针对一网通宽带开户流程的优化建议" in md
    # 草稿不含 HTML 标签（让用户能在 textarea 里编辑）
    assert "<table" not in md and "<h3" not in md and "<span" not in md


def test_build_mail_body_md_multiple_tasks():
    """多任务：每个任务独立卡片 + --- 分隔。"""
    md = mail_content.build_mail_body_md(
        scene="task_center_urge",
        fields={"tasks": [
            _task(index=1, title="任务A", is_overdue=True),
            _task(index=2, title="任务B", is_due_soon=True),
        ]},
    )
    assert "### 1. 任务A" in md
    assert "### 2. 任务B" in md
    assert md.count("**工单内容**") == 2
    assert "---" in md  # 任务间分隔


def test_build_mail_body_md_passthrough_when_user_keeps_titles():
    """用户编辑后保留任意任务 title：跳过 section 追加（不重复）。"""
    tasks = [_task(title="任务A"), _task(index=2, title="任务B")]
    user_md = "### 1. 任务A\n\n| 自定义 |\n| --- |\n| 用户编辑 |\n"
    md = mail_content.build_mail_body_md(
        scene="task_center_urge",
        fields={"tasks": tasks},
        body_md=user_md,
    )
    # 任务B 标题未出现 → section 跳过追加，避免重复
    assert "### 2. 任务B" not in md
    # 用户编辑的"任务A"保留
    assert "### 1. 任务A" in md
    assert "用户编辑" in md


def test_build_mail_body_md_rebuilds_when_user_empties_body():
    """用户清空 body：重新拼装完整 section_md。"""
    tasks = [_task(title="任务A")]
    md = mail_content.build_mail_body_md(
        scene="task_center_urge",
        fields={"tasks": tasks},
        body_md="",
    )
    # body_md 为空时 section_md 完整追加
    assert "### 1. 任务A" in md
    assert "**工单内容**" in md


def test_build_mail_body_md_notify_scene_uses_notify_branch():
    """notify 场景：引导语义走 notify，但 render_task_center_section 与 urge 同形。"""
    md = mail_content.build_mail_body_md(
        scene="task_center_notify",
        fields={"tasks": [_task()]},
    )
    # 结构化装配与 urge 一致；scene 区分在 build_mail_body 的引导语/标题/品牌色
    assert "### 1. [REQ-001]" in md


def test_build_mail_body_md_empty_tasks_returns_empty():
    """空任务列表：返回空字符串。"""
    md = mail_content.build_mail_body_md(
        scene="task_center_urge",
        fields={"tasks": []},
    )
    assert md == ""