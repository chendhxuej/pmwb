"""工单 / 会议 与 Obsidian 笔记的双向联动服务。

职责：
- 一键沉淀：把运营工单 / 会议 生成知识条目 Markdown，写入 Obsidian vault 的
  新目录结构（01-运营知识 / 03-会议资产），并在 pmwb_knowledge_item 建索引，
  同时回填来源对象的 obsidian_path，形成双向关联。
- 落盘位置遵循 docs/需求规格说明书.md 第四节「Obsidian 知识库归档方案」。
"""
from datetime import datetime
from typing import Dict, Optional

from core.config import settings
from core.exceptions import NotFoundException
from db.models import PmwbKnowledgeItem
from services.knowledge import knowledge_item_service
from services.meeting import meeting_service
from services.operation import operation_issue_service
from utils.obsidian import read_markdown, sanitize_filename, write_markdown


def _fmt_dt(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value) if value else "—"


def _gen_item_id() -> str:
    date = datetime.now().strftime("%Y%m%d")
    rand = str(datetime.now().microsecond % 1000).zfill(3)
    return f"KNOW-{date}-{rand}"


def _find_existing_index(db, source_type: str, source_id: str) -> Optional[PmwbKnowledgeItem]:
    return (
        db.query(PmwbKnowledgeItem)
        .filter(
            PmwbKnowledgeItem.source_type == source_type,
            PmwbKnowledgeItem.source_id == source_id,
        )
        .first()
    )


# 运营工单大类 -> (落盘子目录, 笔记模板类型)
ISSUE_SEDIMENT_DIR = {
    "bug": ("Bug解决方案", "bug"),
    "data": ("运营分析案例", "analysis"),
    "prod": ("Bug解决方案", "bug"),
    "complaint": ("运营分析案例", "analysis"),
    "task": ("运维SOP", "sop"),
}


def _build_issue_markdown(issue, note_type: str) -> str:
    lines = [
        "---",
        f"bug_id: {issue.issue_no}",
        f"issue_type: {issue.issue_type}",
        f"category: {issue.category}",
        f"status: {issue.status}",
        f"handler: {issue.handler or ''}",
        f"related_system: {issue.related_system or ''}",
        "source: operation",
        f"created: {_fmt_dt(datetime.now())}",
        "---",
        "",
        f"# {issue.title}",
        "",
        "## 概述",
        f"- 工单编号：{issue.issue_no}",
        f"- 大类：{issue.category}",
        f"- 子类：{issue.issue_type}",
        f"- 状态：{issue.status}",
        f"- 责任人：{issue.handler or '—'}",
        f"- 关联系统：{issue.related_system or '—'}",
        f"- 影响等级：{issue.impact_level or '—'}",
        f"- 发现时间：{_fmt_dt(issue.discovery_date)}",
        f"- 解决时间：{_fmt_dt(issue.resolve_date)}",
        "",
        "## 现象 / 情况说明",
        issue.situation_desc or "（待补充）",
        "",
        "## 根因分析",
        issue.root_cause or "（待补充）",
        "",
        "## 解决方案",
        issue.solution or "（待补充）",
        "",
        "## 预防措施",
        "> 待补充",
        "",
    ]
    if note_type == "sop":
        lines += [
            "## 标准处理步骤",
            "1. （待补充）",
            "",
            "## 责任人 / 复核周期",
            f"- 责任人：{issue.handler or '—'}",
            "- 复核周期：（待补充）",
            "",
        ]
    lines += [
        "## 关联",
        f"- 关联需求：{issue.related_req_id or '—'}",
        f"- 关联开发工单：{issue.related_ticket_no or '—'}",
        "",
    ]
    return "\n".join(lines)


def sediment_operation_issue(db, issue_id: int) -> Dict:
    """把运营工单沉淀为知识条目，返回 {obsidian_path, knowledge_item_id, item_id, created}。"""
    issue = operation_issue_service.get(db, issue_id)
    if not issue:
        raise NotFoundException(f"运营工单不存在：id={issue_id}")

    # 去重：已存在索引则直接返回（幂等）
    existing = _find_existing_index(db, "operation", str(issue.id))
    if existing:
        if not issue.obsidian_path:
            issue.obsidian_path = existing.obsidian_path
            db.commit()
        return {
            "obsidian_path": existing.obsidian_path,
            "knowledge_item_id": existing.id,
            "item_id": existing.item_id,
            "created": False,
        }

    subdir, note_type = ISSUE_SEDIMENT_DIR.get(issue.category, ("Bug解决方案", "bug"))
    filename = f"{sanitize_filename(issue.issue_no)}-{sanitize_filename(issue.title)}.md"
    rel_path = f"01-运营知识/{subdir}/{filename}"

    # 仅当文件不存在时才写，避免覆盖用户已在 Obsidian 中的编辑
    if not read_markdown(rel_path):
        write_markdown(rel_path, _build_issue_markdown(issue, note_type))

    summary = (issue.solution or issue.situation_desc or issue.title)[:200]
    item = knowledge_item_service.create(
        db,
        {
            "item_id": _gen_item_id(),
            "title": issue.title,
            "category": "运营知识",
            "sub_category": subdir,
            "tags": f"运营工单,{issue.issue_type}",
            "obsidian_path": rel_path,
            "source_type": "operation",
            "source_id": str(issue.id),
            "summary": summary,
        },
    )
    issue.obsidian_path = rel_path
    db.commit()
    return {
        "obsidian_path": rel_path,
        "knowledge_item_id": item.id,
        "item_id": item.item_id,
        "created": True,
    }


def _build_meeting_markdown(meeting) -> str:
    """生成会议纪要 Markdown（行业通用五段式 + 标准 YAML frontmatter）。"""
    status_map = {"planned": "待召开", "held": "已召开", "cancelled": "已取消"}
    mt_status = status_map.get(meeting.status, "待处理")
    type_map = {
        "requirement_discussion": "需求讨论",
        "problem_analysis": "问题分析",
        "internal_regular": "内部例会",
        "external_sync": "外部对接",
        "party_meeting": "党会",
        "group_meeting": "集团会议",
        "other": "其他",
    }
    tlabel = type_map.get(meeting.meeting_type, "其他")

    def fdt(v):
        return v.strftime("%Y-%m-%d %H:%M") if v else "—"

    def fdate(v):
        return v.strftime("%Y-%m-%d") if v else "—"

    # 参会人
    attendees = meeting.attendees or []
    att_lines = (
        "\n".join(
            f"- {a.name}（{a.dept or '—'}{'，必到' if a.is_required else '，可选'}）"
            for a in attendees
        )
        or "（无）"
    )
    absent = (meeting.absentees or "").strip() or "（无）"

    # 议程与讨论
    agendas = sorted(meeting.agendas or [], key=lambda x: (x.seq or 0, x.id or 0))
    if agendas:
        blocks = []
        for i, ag in enumerate(agendas, 1):
            b = [
                f"### {i}. {ag.topic}",
                "- 讨论要点：",
                f"- 结论/决议：{ag.conclusion or '（待补充）'}",
            ]
            if ag.division:
                b.append(f"- 分工：{ag.division}")
            blocks.append("\n".join(b))
        agenda_block = "\n\n".join(blocks)
    else:
        agenda_block = "（待补充）"

    # 待办事项表
    actions = meeting.actions or []
    if actions:
        rows = [
            "| 序号 | 任务 | 负责人 | 截止日期 | 优先级 | 状态 | 模板 |",
            "|------|------|--------|----------|--------|------|------|",
        ]
        for i, a in enumerate(actions, 1):
            due = fdate(a.due_date) if a.due_date else "—"
            rows.append(
                f"| {i} | {a.content or '—'} | {a.owner or '待定'} | {due} | {a.category or '—'} | {a.status or 'pending'} | {a.template or '—'} |"
            )
        action_block = "\n".join(rows)
    else:
        action_block = "（无）"

    conclusion = meeting.summary or "（见各议题结论）"

    # 动态标签
    tags = ["会议", tlabel]
    if meeting.related_req_id:
        tags.append("需求")
    tags_str = ", ".join(tags)

    # 标准 YAML frontmatter（ascii 键、引号值）
    fm = [
        "---",
        f'meeting_title: "{meeting.title}"',
        f'meeting_type: "{tlabel}"',
        f"status: {meeting.status}",
        f"date: {fdate(meeting.start_time)}",
        f"start_time: {fdt(meeting.start_time)}",
        f"end_time: {fdt(meeting.end_time)}",
        "timezone: Asia/Shanghai",
        f'host: "{meeting.host or ""}"',
        f'recorder: "{meeting.recorder or ""}"',
        f'location: "{meeting.location or ""}"',
        f"tags: [{tags_str}]",
        f'related_req_id: "{meeting.related_req_id or ""}"',
        f'related_ticket_no: "{meeting.related_ticket_no or ""}"',
        "---",
    ]

    body = [
        f"# {meeting.title}",
        "",
        "## 一、会议信息",
        f"- 主持人：{meeting.host or '—'}",
        f"- 记录人：{meeting.recorder or '—'}",
        f"- 时间：{fdt(meeting.start_time)} ~ {fdt(meeting.end_time)}",
        f"- 地点/方式：{meeting.location or '—'}",
        f"- 参会人：\n{att_lines}",
        f"- 缺席人：{absent}",
        f"- 参会注意点：{meeting.attendee_notes or '—'}",
        "",
        "## 二、会议议程与讨论",
        agenda_block,
        "",
        "## 三、会议决议（核心）",
        conclusion,
        "",
        "## 四、待办事项（行动项）",
        action_block,
        "",
        "## 五、下次会议",
        "- 时间：",
        "- 待跟进议题：",
        "",
        "## 关联",
        f"- 需求：[[{meeting.related_req_id}]]" if meeting.related_req_id else "- 需求：",
        f"- 工单：[[{meeting.related_ticket_no}]]" if meeting.related_ticket_no else "- 工单：",
        "",
    ]
    return "\n".join(fm + [""] + body)


# 会议纪要落盘目录（与 Obsidian vault 真实结构一致，修正原 03-会议资产 错路径）
MEETING_SEDIMENT_DIR = "05-会议纪要"


def sediment_meeting(db, meeting_id: int) -> Dict:
    """把会议沉淀为知识条目，返回 {obsidian_path, knowledge_item_id, item_id, created}。"""
    meeting = meeting_service.get(db, meeting_id)
    if not meeting:
        raise NotFoundException(f"会议不存在：id={meeting_id}")

    existing = _find_existing_index(db, "meeting", str(meeting.id))
    if existing:
        if not meeting.obsidian_path:
            meeting.obsidian_path = existing.obsidian_path
            db.commit()
        return {
            "obsidian_path": existing.obsidian_path,
            "knowledge_item_id": existing.id,
            "item_id": existing.item_id,
            "created": False,
        }

    day = (meeting.start_time or datetime.now()).strftime("%Y%m%d")
    filename = f"【{day}】{sanitize_filename(meeting.title)}.md"
    rel_path = f"{MEETING_SEDIMENT_DIR}/{filename}"

    if not read_markdown(rel_path):
        write_markdown(rel_path, _build_meeting_markdown(meeting))

    summary = (meeting.summary or meeting.title)[:200]
    item = knowledge_item_service.create(
        db,
        {
            "item_id": _gen_item_id(),
            "title": meeting.title,
            "category": "meeting",
            "sub_category": meeting.meeting_type,
            "tags": "会议纪要",
            "obsidian_path": rel_path,
            "source_type": "meeting",
            "source_id": str(meeting.id),
            "summary": summary,
        },
    )
    meeting.obsidian_path = rel_path
    db.commit()
    return {
        "obsidian_path": rel_path,
        "knowledge_item_id": item.id,
        "item_id": item.item_id,
        "created": True,
    }
