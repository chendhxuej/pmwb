"""工单 / 会议 / 需求 与 Obsidian 笔记的双向联动服务。

职责：
- 一键沉淀：把运营工单 / 会议 / 需求 / 开发工单 生成知识条目 Markdown，写入 Obsidian vault
  的对应目录，并在 pmwb_knowledge_item 建索引，同时回填来源对象的 obsidian_path，形成双向关联。
  - 需求知识笔记同置到需求自身文件夹（业务建设/需求分析说明书/{req_id}_{safe(req_name)}/）；
  - 运营/会议/开发交付经 P0 路径权威源归入 01-业务知识/{领域}/ 树（见 resolve_domain_path）。
- 沉淀时按 domain_code 回链到对应业务知识主笔记，并写 pmwb_knowledge_link（主笔记已存在时）。
- 落盘位置遵循 docs/需求规格说明书.md 第四节「Obsidian 知识库归档方案」。
"""
import os
import json
import shutil
from datetime import datetime
from typing import Dict, List, Optional

from core.config import settings
from core.exceptions import NotFoundException
from db.models import (
    PmwbBusinessDomain,
    PmwbDevDeliverable,
    PmwbDevTicket,
    PmwbDevTicketLog,
    PmwbKnowledgeItem,
    PmwbMeeting,
    PmwbOperationIssue,
    PmwbRequirementExt,
    PmwbUserStory,
    SentEmail,
)
from services.knowledge import knowledge_item_service
from services.knowledge_link_service import ensure_domain_main_note, link_note
from services.meeting import meeting_service
from services.operation import operation_issue_service
from utils.obsidian import (
    append_or_replace_section,
    delete_markdown,
    read_frontmatter,
    read_markdown,
    sanitize_filename,
    write_frontmatter,
    write_markdown,
)


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


# 运营工单大类 -> (落盘子目录完整路径, 笔记模板类型)
ISSUE_SEDIMENT_DIR = {
    "bug": ("11-业务运营/Bug解决方案", "bug"),
    "data": ("11-业务运营/运营分析案例", "analysis"),
    "prod": ("11-业务运营/Bug解决方案", "bug"),
    "complaint": ("11-业务运营/运营分析案例", "analysis"),
    "task": ("11-业务运营/运维SOP", "sop"),
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


def sediment_operation_issue(db, issue_id: int, force: bool = False) -> Dict:
    """把运营工单沉淀为知识条目，返回 {obsidian_path, knowledge_item_id, item_id, created}。

    force=True 时覆盖已存在的工单知识文件。
    """
    issue = operation_issue_service.get(db, issue_id)
    if not issue:
        raise NotFoundException(f"运营工单不存在：id={issue_id}")

    # 去重：已存在索引则直接返回（幂等，除非 force 覆盖）
    existing = _find_existing_index(db, "operation", str(issue.id))
    if existing and not force:
        if not issue.obsidian_path:
            issue.obsidian_path = existing.obsidian_path
            db.commit()
        return {
            "obsidian_path": existing.obsidian_path,
            "knowledge_item_id": existing.id,
            "item_id": existing.item_id,
            "created": False,
        }

    subdir, note_type = ISSUE_SEDIMENT_DIR.get(issue.category, ("11-业务运营/Bug解决方案", "bug"))
    filename = f"{sanitize_filename(issue.issue_no)}-{sanitize_filename(issue.title)}.md"
    rel_path = f"{subdir}/{filename}"

    md = _build_issue_markdown(issue, note_type)
    if force and read_markdown(rel_path):
        write_markdown(rel_path, md)
    elif not read_markdown(rel_path):
        write_markdown(rel_path, md)

    if existing:
        issue.obsidian_path = rel_path
        db.commit()
        return {
            "obsidian_path": rel_path,
            "knowledge_item_id": existing.id,
            "item_id": existing.item_id,
            "created": False,
        }

    summary = (issue.solution or issue.situation_desc or issue.title)[:200]
    item = knowledge_item_service.create(
        db,
        {
            "item_id": _gen_item_id(),
            "title": issue.title,
            "category": "运营知识",
            "sub_category": subdir.split("/")[-1] if "/" in subdir else subdir,
            "tags": f"运营工单,{issue.issue_type}",
            "obsidian_path": rel_path,
            "source_type": "operation",
            "source_id": str(issue.id),
            "domain_code": getattr(issue, "domain_code", None),
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
            if ag.background and str(ag.background).strip():
                b.append(f"- 议题背景：{ag.background}")
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

    # 会议决议（核心）：由各议题结论聚合，不再依赖会议纪要摘要输入
    conclusion_items = [
        f"{i}. **{ag.topic or ('议题' + str(i))}**：{(ag.conclusion or '').strip()}"
        for i, ag in enumerate(agendas, 1)
        if (ag.conclusion or "").strip()
    ]
    conclusion = "\n".join(conclusion_items) if conclusion_items else "（待补充）"

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


def sediment_meeting(db, meeting_id: int, force: bool = False) -> Dict:
    """把会议沉淀为知识条目，返回 {obsidian_path, knowledge_item_id, item_id, created}。

    force=True 时覆盖已存在的纪要文件与索引（用于会议内容更新后重新生成）。
    """
    meeting = meeting_service.get(db, meeting_id)
    if not meeting:
        raise NotFoundException(f"会议不存在：id={meeting_id}")

    existing = _find_existing_index(db, "meeting", str(meeting.id))
    if existing and not force:
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

    md = _build_meeting_markdown(meeting)
    if force and read_markdown(rel_path):
        write_markdown(rel_path, md)
    elif not read_markdown(rel_path):
        write_markdown(rel_path, md)

    if existing:
        meeting.obsidian_path = rel_path
        db.commit()
        return {
            "obsidian_path": rel_path,
            "knowledge_item_id": existing.id,
            "item_id": existing.item_id,
            "created": False,
        }

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
            "domain_code": getattr(meeting, "domain_code", None),
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


def delete_meeting_minutes(db, meeting_id: int) -> Dict:
    """删除会议纪要：清理 Obsidian 文件、知识索引与关联记录。"""
    from services.knowledge_link import _sync_backlinks  # noqa: WPS433
    from db.models import PmwbKnowledgeLink

    meeting = meeting_service.get(db, meeting_id)
    if not meeting:
        raise NotFoundException(f"会议不存在：id={meeting_id}")

    existing = _find_existing_index(db, "meeting", str(meeting.id))
    removed_path = None
    if existing:
        removed_path = existing.obsidian_path
        # 清理反链
        _sync_backlinks(db, existing.id)
        # 删除关联记录
        db.query(PmwbKnowledgeLink).filter(
            PmwbKnowledgeLink.knowledge_item_id == existing.id
        ).delete(synchronize_session=False)
        knowledge_item_service.delete(db, existing.id)
        delete_markdown(removed_path)
    meeting.obsidian_path = None
    db.commit()
    return {"removed_path": removed_path, "removed": bool(existing)}


# ---------------------------------------------------------------------------
# 需求沉淀（知识笔记同置到需求自身文件夹 业务建设/需求分析说明书/{req_id}_{safe(req_name)}/）
# ---------------------------------------------------------------------------


def _build_requirement_markdown(ext, email, stories, dev_tickets, meetings, issues, main_note_title: Optional[str] = None) -> str:
    """生成需求知识沉淀 Markdown。main_note_title 非空时在 frontmatter 与正文写回链到主笔记。"""
    # 优先使用 ext 中的覆盖值，回退到 email
    req_name = (ext.req_name if ext and ext.req_name else (email.req_name if email else "未知需求"))
    background = (ext.background if ext and ext.background else (email.background if email else ""))
    description = (ext.description if ext and ext.description else (email.description if email else ""))
    clarification = (ext.clarification if ext and ext.clarification else (email.clarification if email else ""))
    system_name = (ext.system_name if ext and ext.system_name else (email.system_name if email else ""))
    sa_name = (ext.sa_name if ext and ext.sa_name else (email.sa_name if email else ""))
    proposer = email.proposer if email else ""
    propose_time = _fmt_dt(email.propose_time) if email and email.propose_time else "—"

    domain_code = getattr(ext, "domain_code", None) if ext else None

    fm = [
        "---",
        f'title: "{req_name}"',
        f"req_id: {ext.req_id if ext else (email.req_id if email else '')}",
        f'domain_code: "{domain_code or ""}"',
        f"source_type: requirement",
        f"status: draft",
        f"created: {_fmt_dt(datetime.now())}",
        f"tags: [需求, {system_name or '通用'}]",
    ]
    if main_note_title:
        fm.append(f'related_business_main_note: "{main_note_title}"')
    fm += [
        "---",
        "",
        f"# {req_name}",
        "",
        "## 概述",
        f"- 需求编号：{ext.req_id if ext else (email.req_id if email else '—')}",
        f"- 提出人：{proposer or '—'}",
        f"- 提出时间：{propose_time}",
        f"- 涉及系统：{system_name or '—'}",
        f"- SA：{sa_name or '—'}",
        f"- 业务领域：{domain_code or '—'}",
        f"- 跟踪状态：{ext.status if ext else '—'}",
        f"- 优先级：{ext.priority if ext else '—'}",
        "",
        "## 需求背景",
        background or "（待补充）",
        "",
        "## 需求描述",
        description or "（待补充）",
        "",
    ]
    if clarification:
        fm += [
            "## 澄清内容",
            clarification,
            "",
        ]

    # 用户故事
    if stories:
        fm += ["## 用户故事", ""]
        for i, s in enumerate(stories, 1):
            fm += [
                f"### 故事{i}：{s.title or '—'}",
                f"- 描述：{s.desc or '—'}",
                f"- 场景：{s.scene or '—'}",
            ]
            if s.acceptance:
                fm.append(f"- 验收标准：{s.acceptance}")
            if s.rules:
                fm.append(f"- 业务规则：{s.rules}")
            fm.append(f"- 定稿：{'是' if s.finalized else '否'}")
            fm.append("")
    else:
        fm += ["## 用户故事", "（暂无）", ""]

    # 关联
    fm += ["## 关联", ""]
    if main_note_title:
        fm += [
            f"### 业务知识主笔记",
            f"- 回链：[[{main_note_title}]]",
            "",
        ]
    if dev_tickets:
        fm.append("### 关联开发工单")
        for t in dev_tickets:
            fm.append(f"- [[{t.ticket_no}]] - {t.system_name} ({t.status})")
        fm.append("")
    if meetings:
        fm.append("### 关联会议")
        for m in meetings:
            fm.append(f"- [[{m.title}]] ({_fmt_dt(m.start_time)})")
        fm.append("")
    if issues:
        fm.append("### 关联运营工单")
        for iss in issues:
            fm.append(f"- [[{iss.issue_no}]] - {iss.title} ({iss.status})")
        fm.append("")

    if domain_code:
        fm += [
            "### 业务知识",
            f"- 业务领域编码：{domain_code}",
            "",
        ]

    return "\n".join(fm)


def sediment_requirement(db, req_id: str, force: bool = False) -> Dict:
    """把需求沉淀为知识条目，返回 {obsidian_path, knowledge_item_id, item_id, created}。

    force=True 时覆盖已存在的需求知识文件（用于需求更新后重新沉淀）。
    """
    # 查找需求扩展信息
    ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == req_id).first()
    # 查找原始邮件信息
    email = db.query(SentEmail).filter(SentEmail.req_id == req_id).first()
    if not ext and not email:
        raise NotFoundException(f"需求不存在：req_id={req_id}")

    domain_code = getattr(ext, "domain_code", None) if ext else None
    # 主笔记已存在时回链（不主动创建主笔记，仅当 domain 已建立主笔记时打通双向链接）
    main_note = _find_main_note(db, domain_code)
    main_note_title = main_note.title if main_note else None

    # 幂等：已存在索引则不重复创建（除非 force 覆盖）
    existing = _find_existing_index(db, "requirement", req_id)
    if existing and not force:
        # 仍确保与主笔记的关联存在（历史沉淀可能未回链）
        if main_note:
            try:
                link_note(db, main_note.id, source_type="requirement", source_id=req_id,
                           link_type="main", domain_code=domain_code)
            except Exception:
                pass
        return {
            "obsidian_path": existing.obsidian_path,
            "knowledge_item_id": existing.id,
            "item_id": existing.item_id,
            "created": False,
        }

    # 聚合关联数据
    stories = db.query(PmwbUserStory).filter(PmwbUserStory.req_id == req_id).order_by(PmwbUserStory.seq).all()
    dev_tickets = db.query(PmwbDevTicket).filter(PmwbDevTicket.req_id == req_id).all()
    meetings = db.query(PmwbMeeting).filter(PmwbMeeting.related_req_id == req_id).all()
    issues = db.query(PmwbOperationIssue).filter(PmwbOperationIssue.related_req_id == req_id).all()

    req_name = (ext.req_name if ext and ext.req_name else (email.req_name if email else req_id))
    # 同置：需求知识笔记写入需求自身文件夹（业务建设/需求分析说明书/{req_id}_{safe(req_name)}/），
    # 与需求分析说明书/附件同目录，不再漂到独立的 10-业务建设/需求沉淀 树。
    from services import requirement_delivery
    folder_abs = requirement_delivery._resolve_paths(req_id, req_name)["folder"]
    rel_folder = os.path.relpath(folder_abs, settings.OBSIDIAN_VAULT_PATH)
    filename = f"{requirement_delivery._safe_name(req_name or req_id)}-知识沉淀.md"
    rel_path = os.path.join(rel_folder, filename)

    md = _build_requirement_markdown(ext, email, stories, dev_tickets, meetings, issues, main_note_title=main_note_title)
    if force and read_markdown(rel_path):
        write_markdown(rel_path, md)
    elif not read_markdown(rel_path):
        write_markdown(rel_path, md)

    if existing:
        # 历史索引（多为 force 覆盖场景）：重新关联主笔记
        if main_note:
            try:
                link_note(db, main_note.id, source_type="requirement", source_id=req_id,
                           link_type="main", domain_code=domain_code)
            except Exception:
                pass
        return {
            "obsidian_path": rel_path,
            "knowledge_item_id": existing.id,
            "item_id": existing.item_id,
            "created": False,
        }

    background_text = (ext.background if ext and ext.background else (email.background if email else "")) or ""
    summary = (background_text[:200] if background_text else req_name)
    item = knowledge_item_service.create(
        db,
        {
            "item_id": _gen_item_id(),
            "title": req_name,
            "category": "requirement",
            "sub_category": system_name if (system_name := (ext.system_name if ext and ext.system_name else (email.system_name if email else ""))) else None,
            "tags": f"需求,{system_name or '通用'}",
            "obsidian_path": rel_path,
            "source_type": "requirement",
            "source_id": req_id,
            "domain_code": domain_code,
            "summary": summary,
        },
    )
    # 新建沉淀：若主笔记已存在，注册需求→主笔记的关联并同步主笔记索引
    if main_note:
        try:
            link_note(db, main_note.id, source_type="requirement", source_id=req_id,
                       link_type="main", domain_code=domain_code)
        except Exception:
            pass
    return {
        "obsidian_path": rel_path,
        "knowledge_item_id": item.id,
        "item_id": item.item_id,
        "created": True,
    }


def _find_main_note(db, domain_code: Optional[str]):
    """查找某领域已存在的业务知识主笔记（不主动创建）。"""
    if not domain_code:
        return None
    return (
        db.query(PmwbKnowledgeItem)
        .filter(PmwbKnowledgeItem.domain_code == domain_code)
        .filter(PmwbKnowledgeItem.note_type == "main")
        .first()
    )


def _item_public_dict(item: PmwbKnowledgeItem) -> dict:
    return {
        "id": item.id,
        "item_id": item.item_id,
        "title": item.title,
        "obsidian_path": item.obsidian_path,
        "domain_code": item.domain_code,
        "note_type": getattr(item, "note_type", "sub"),
        "sub_category": item.sub_category,
        "summary": item.summary,
    }


def _ensure_scenario_rules_sub_note(db, domain_code: str) -> dict:
    """确保某领域存在「场景规则」子笔记（03-业务规则/场景规则.md），返回 item 字典。

    找不到则按 domain_code 自动创建（kc-2-3 规则沉淀前置）。
    注：模型仅有 note_type/sub_category（kc-2-2 实现），sub_type 概念以 sub_category 承载。
    """
    if not domain_code:
        raise NotFoundException("需求未设置业务领域(domain_code)，无法沉淀规则")
    domain = db.query(PmwbBusinessDomain).filter(PmwbBusinessDomain.domain_code == domain_code).first()
    if not domain:
        raise NotFoundException(f"业务领域不存在：{domain_code}")
    existing = (
        db.query(PmwbKnowledgeItem)
        .filter(PmwbKnowledgeItem.domain_code == domain_code)
        .filter(PmwbKnowledgeItem.sub_category == "场景规则")
        .first()
    )
    if existing:
        return _item_public_dict(existing)

    subdir = f"01-业务知识/{domain.domain_group}/{domain.domain_name}/03-业务规则"
    title = f"{domain.domain_name} 场景规则"
    rel_path = f"{subdir}/{title}.md"
    fm = [
        "---",
        f'item_id: "KNOW-{datetime.now().strftime("%Y%m%d")}-{str(datetime.now().microsecond % 1000).zfill(3)}"',
        f'domain_code: "{domain_code}"',
        f'domain_name: "{domain.domain_name}"',
        'note_type: "sub"',
        'sub_category: "场景规则"',
        f'title: "{title}"',
        f'created: {_fmt_dt(datetime.now())}',
        "tags: [业务规则, 场景规则]",
        "---",
        "",
        f"# {title}",
        "",
        "> 本笔记沉淀来自需求用户故事的「场景规则」，由系统自动追加维护。",
        "",
        "## 沉淀自用户故事的规则",
        "",
        "> 以下由各需求「沉淀业务规则」操作自动追加，每条以 `### 需求编号` 为界，可重复触发更新。",
        "",
    ]
    write_markdown(rel_path, "\n".join(fm))
    item = knowledge_item_service.create(
        db,
        {
            "item_id": f"KNOW-{datetime.now().strftime('%Y%m%d')}-{str(datetime.now().microsecond % 1000).zfill(3)}",
            "title": title,
            "category": "业务规则",
            "sub_category": "场景规则",
            "tags": "业务规则,场景规则",
            "obsidian_path": rel_path,
            "source_type": "manual",
            "source_id": domain_code,
            "domain_code": domain_code,
            "note_type": "sub",
            "summary": f"{domain.domain_name} 场景规则（沉淀自需求用户故事）",
        },
    )
    # 领域归属时保活主笔记并重建子笔记摘要
    try:
        ensure_domain_main_note(db, domain_code)
    except Exception:
        pass
    return _item_public_dict(item)


def sediment_requirement_rules(db, req_id: str) -> Dict:
    """把某需求的用户故事业务规则追加到目标领域主笔记的「场景规则」子笔记。

    规则以「### 需求编号」为界追加，重复触发时同需求规则块被覆盖更新（不重复堆积）。
    同时在 pmwb_knowledge_link 记录需求与场景规则子笔记的关联。
    """
    ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == req_id).first()
    domain_code = getattr(ext, "domain_code", None) if ext else None
    if not domain_code:
        raise NotFoundException("需求未设置业务领域(domain_code)，无法沉淀规则")

    stories = (
        db.query(PmwbUserStory)
        .filter(PmwbUserStory.req_id == req_id)
        .filter(PmwbUserStory.finalized == 1)
        .order_by(PmwbUserStory.seq)
        .all()
    )
    stories = [s for s in stories if s.rules]
    if not stories:
        raise NotFoundException("该需求暂无「已定稿且含业务规则」的用户故事，无法沉淀")

    sub_note = _ensure_scenario_rules_sub_note(db, domain_code)
    req_name = (ext.req_name if ext and ext.req_name else req_id)

    # 按需求聚合的规则块（以 ### 需求编号 为界，便于重复触发时整体替换）
    block_lines = [f"> 来源需求：{req_id}（{req_name}）", ""]
    for i, s in enumerate(stories, 1):
        block_lines.append(f"#### 故事{i}：{s.title or '—'}")
        rules = s.rules
        if isinstance(rules, str):
            try:
                rules = json.loads(rules)
            except Exception:
                rules = []
        if not isinstance(rules, list):
            rules = []
        for r in rules:
            block_lines.append(f"- {r}")
        block_lines.append("")
    block = "\n".join(block_lines).rstrip()

    content = read_markdown(sub_note["obsidian_path"]) or ""
    new_content = append_or_replace_section(content, f"场景规则 · {req_id}", block)
    write_markdown(sub_note["obsidian_path"], new_content)

    # 记录需求 → 场景规则子笔记 的关联（canonical）
    try:
        link_note(db, sub_note["id"], source_type="requirement", source_id=req_id,
                   link_type="sub", domain_code=domain_code, note="业务规则")
    except Exception:
        pass

    return {
        "sub_note_id": sub_note["id"],
        "sub_note_title": sub_note["title"],
        "obsidian_path": sub_note["obsidian_path"],
        "stories_sedimented": len(stories),
    }


# 运营工单结构化字段枚举中文标签（用于沉淀到场景规则子笔记时的人类可读展示）
OPERATION_ROOT_CAUSE_LABELS = {
    "system_config": "系统配置问题",
    "business_rule": "业务规则问题",
    "data_issue": "数据问题",
    "process_gap": "流程缺口",
    "external_dependency": "外部依赖",
    "other": "其他",
}
OPERATION_IMPACT_SCOPE_LABELS = {
    "single_customer": "单个客户",
    "partial_region": "部分区域",
    "full_region": "全区域",
    "business_line": "业务线",
    "platform": "平台级",
}
OPERATION_SOLUTION_TYPE_LABELS = {
    "config_fix": "配置修复",
    "code_fix": "代码修复",
    "data_repair": "数据修复",
    "process_optimization": "流程优化",
    "training": "培训",
    "escalation": "升级处理",
    "other": "其他",
}


def sediment_operation_rules(db, issue_id: int) -> Dict:
    """把运营工单的结构化经验（根因分类/影响范围/解决方案类型/根因/解决方案/经验总结）追加到
    目标领域主笔记的「场景规则」子笔记。

    以「### 工单编号」为界追加，重复触发时同工单规则块被覆盖更新（不重复堆积）。
    同时在 pmwb_knowledge_link 记录工单与场景规则子笔记的关联。
    """
    issue = operation_issue_service.get(db, issue_id)
    if not issue:
        raise NotFoundException(f"运营工单不存在：id={issue_id}")
    domain_code = getattr(issue, "domain_code", None)
    if not domain_code:
        raise NotFoundException("运营工单未设置业务领域(domain_code)，无法沉淀规则")

    sub_note = _ensure_scenario_rules_sub_note(db, domain_code)

    # 结构化规则块（以 ### 工单编号 为界，便于重复触发时整体替换）
    lines = [
        f"> 来源工单：{issue.issue_no}（{issue.title}）",
        "",
        f"- 根因分类：{OPERATION_ROOT_CAUSE_LABELS.get(issue.root_cause_type, issue.root_cause_type or '—')}",
        f"- 影响范围：{OPERATION_IMPACT_SCOPE_LABELS.get(issue.impact_scope, issue.impact_scope or '—')}",
        f"- 解决方案类型：{OPERATION_SOLUTION_TYPE_LABELS.get(issue.solution_type, issue.solution_type or '—')}",
        "",
    ]
    if issue.root_cause:
        lines += ["**根因分析**", "", issue.root_cause, ""]
    if issue.solution:
        lines += ["**解决方案**", "", issue.solution, ""]
    if issue.lesson_learned:
        lines += ["**经验总结 / 预防措施**", "", issue.lesson_learned, ""]
    block = "\n".join(lines).rstrip()

    content = read_markdown(sub_note["obsidian_path"]) or ""
    new_content = append_or_replace_section(content, f"场景规则 · {issue.issue_no}", block)
    write_markdown(sub_note["obsidian_path"], new_content)

    # 记录工单 → 场景规则子笔记 的关联（canonical）
    try:
        link_note(db, sub_note["id"], source_type="operation", source_id=str(issue_id),
                   link_type="sub", domain_code=domain_code, note="业务规则")
    except Exception:
        pass

    return {
        "sub_note_id": sub_note["id"],
        "sub_note_title": sub_note["title"],
        "obsidian_path": sub_note["obsidian_path"],
        "issue_sedimented": issue.issue_no,
    }


def archive_requirement_manual(db, req_id: str) -> Dict:
    """把需求关联开发工单中的操作手册交付物归档到业务知识交付物目录并登记主笔记。

    复制交付物文件到 01-业务知识/{group}/{name}/05-交付物/attachments/，
    并在主笔记 frontmatter `related_deliverables` 登记（主笔记已存在时）。
    返回 {archived: [...], skipped: [...], main_note: title|None}。
    """
    ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == req_id).first()
    domain_code = getattr(ext, "domain_code", None) if ext else None
    if not domain_code:
        raise NotFoundException("需求未设置业务领域(domain_code)，无法归档操作手册")

    main_note = _find_main_note(db, domain_code)
    domain = db.query(PmwbBusinessDomain).filter(PmwbBusinessDomain.domain_code == domain_code).first()
    if not domain:
        raise NotFoundException(f"业务领域不存在：{domain_code}")

    attachments_dir = f"01-业务知识/{domain.domain_group}/{domain.domain_name}/05-交付物/attachments"

    tickets = db.query(PmwbDevTicket).filter(PmwbDevTicket.req_id == req_id).all()
    ticket_ids = [t.id for t in tickets]
    archived = []
    skipped = []
    if ticket_ids:
        deliverables = (
            db.query(PmwbDevDeliverable)
            .filter(PmwbDevDeliverable.ticket_id.in_(ticket_ids))
            .filter(PmwbDevDeliverable.deliverable_type == "operation_manual")
            .all()
        )
        for d in deliverables:
            src = d.obsidian_path or d.local_path
            if not src:
                skipped.append({"file_name": d.file_name, "reason": "无源文件路径"})
                continue
            vault = settings.OBSIDIAN_VAULT_PATH
            src_path = os.path.join(vault, src) if not os.path.isabs(src) else src
            if not os.path.exists(src_path):
                skipped.append({"file_name": d.file_name, "reason": "源文件不存在"})
                continue
            dst_rel = f"{attachments_dir}/{sanitize_filename(d.file_name)}"
            dst_path = os.path.join(vault, dst_rel)
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            shutil.copy2(src_path, dst_path)
            archived.append({"file_name": d.file_name, "obsidian_path": dst_rel})

    # 登记主笔记 frontmatter related_deliverables（主笔记已存在时）
    if main_note and main_note.obsidian_path:
        fm = read_frontmatter(main_note.obsidian_path)
        existing = fm.get("related_deliverables")
        existing_list = existing if isinstance(existing, list) else ([existing] if existing else [])
        changed = False
        for a in archived:
            if a["file_name"] not in existing_list:
                existing_list.append(a["file_name"])
                changed = True
        if changed:
            fm["related_deliverables"] = existing_list
            write_frontmatter(main_note.obsidian_path, fm)

    # 标记需求已归档
    if ext:
        ext.manual_archived = 1
        if archived:
            ext.manual_obsidian_path = archived[0]["obsidian_path"]
        db.commit()

    return {
        "req_id": req_id,
        "archived": archived,
        "skipped": skipped,
        "main_note": main_note.title if main_note else None,
    }


# ---------------------------------------------------------------------------
# 用户故事业务规则沉淀
# ---------------------------------------------------------------------------

USER_STORY_RULE_DIR = "10-业务建设/业务规则"


def _build_user_story_rule_markdown(story, req_id: str, domain_code: str) -> str:
    rules = story.rules or []
    rule_lines = "\n".join(f"{i+1}. {r}" for i, r in enumerate(rules)) or "（暂无）"
    fm = [
        "---",
        f'title: "{story.title or "业务规则"} · 业务规则"',
        f"req_id: {req_id}",
        f'domain_code: "{domain_code or ""}"',
        "source_type: user_story",
        "created: " + _fmt_dt(datetime.now()),
        "tags: [业务规则, 用户故事]",
        "---",
        "",
        f"# {story.title or '用户故事'} · 业务规则",
        "",
        f"- 关联需求：{req_id}",
        f"- 业务领域：{domain_code or '—'}",
        "",
        "## 业务规则",
        rule_lines,
        "",
        "## 故事描述",
        story.desc or "（待补充）",
        "",
        "## 场景",
        story.scene or "（待补充）",
        "",
    ]
    return "\n".join(fm)


def sediment_user_story(db, story_id: int, force: bool = False) -> Dict:
    """把用户故事的业务规则沉淀为知识笔记（业务规则知识），并关联到所属需求。

    force=True 时覆盖已存在的规则笔记。
    """
    story = db.query(PmwbUserStory).filter(PmwbUserStory.id == story_id).first()
    if not story:
        raise NotFoundException(f"用户故事不存在：id={story_id}")
    rules = story.rules or []
    if not rules:
        raise NotFoundException("该用户故事暂无业务规则，无法沉淀")

    req_id = story.req_id
    ext = db.query(PmwbRequirementExt).filter(PmwbRequirementExt.req_id == req_id).first()
    domain_code = getattr(ext, "domain_code", None) if ext else None

    existing = _find_existing_index(db, "user_story", str(story_id))
    if existing and not force:
        return {
            "obsidian_path": existing.obsidian_path,
            "knowledge_item_id": existing.id,
            "item_id": existing.item_id,
            "created": False,
        }

    filename = f"{sanitize_filename(req_id)}-{sanitize_filename(story.title or 'story')}-规则.md"
    rel_path = f"{USER_STORY_RULE_DIR}/{filename}"
    md = _build_user_story_rule_markdown(story, req_id, domain_code)
    if force and read_markdown(rel_path):
        write_markdown(rel_path, md)
    elif not read_markdown(rel_path):
        write_markdown(rel_path, md)

    if existing:
        return {
            "obsidian_path": rel_path,
            "knowledge_item_id": existing.id,
            "item_id": existing.item_id,
            "created": False,
        }

    from services.knowledge_link import link_to_item  # noqa: WPS433

    summary = (rules[0] or "")[:200]
    item = knowledge_item_service.create(
        db,
        {
            "item_id": _gen_item_id(),
            "title": f"{story.title or '用户故事'} · 业务规则",
            "category": "requirement",
            "sub_category": "业务规则",
            "tags": "业务规则,用户故事",
            "obsidian_path": rel_path,
            "source_type": "user_story",
            "source_id": str(story_id),
            "domain_code": domain_code,
            "summary": summary,
        },
    )
    # 关联到所属需求，便于需求详情页查看
    link_to_item(db, "requirement", req_id, item.id, link_type="sub", note="业务规则", domain_code=domain_code)
    return {
        "obsidian_path": rel_path,
        "knowledge_item_id": item.id,
        "item_id": item.item_id,
        "created": True,
    }


# ---------------------------------------------------------------------------
# 开发工单沉淀
# ---------------------------------------------------------------------------

DEV_TICKET_SEDIMENT_DIR = "14-知识沉淀/开发交付"


def _build_dev_ticket_markdown(ticket, deliverables, logs, email) -> str:
    """生成开发工单知识沉淀 Markdown。"""
    domain_code = getattr(ticket, "domain_code", None)
    req_name = email.req_name if email else ""

    fm = [
        "---",
        f'title: "{ticket.ticket_no} - {ticket.system_name}"',
        f"ticket_no: {ticket.ticket_no}",
        f"req_id: {ticket.req_id}",
        f'domain_code: "{domain_code or ""}"',
        f"source_type: ticket",
        f"status: {ticket.status}",
        f"progress: {ticket.progress}",
        f"created: {_fmt_dt(datetime.now())}",
        f"tags: [开发工单, {ticket.system_name or '通用'}]",
        "---",
        "",
        f"# {ticket.ticket_no} - {ticket.system_name}",
        "",
        "## 概述",
        f"- 工单编号：{ticket.ticket_no}",
        f"- 关联需求：{ticket.req_id}" + (f"（{req_name}）" if req_name else ""),
        f"- 涉及系统：{ticket.system_name}",
        f"- 开发团队：{ticket.dev_team or '—'}",
        f"- 开发负责人：{ticket.developer or '—'}",
        f"- 业务领域：{domain_code or '—'}",
        f"- 状态：{ticket.status}",
        f"- 进度：{ticket.progress}%",
        f"- 优先级：{ticket.priority}",
        "",
        "## 开发内容",
        ticket.description or "（待补充）",
        "",
    ]

    if ticket.risk_note:
        fm += ["## 风险/延期说明", ticket.risk_note, ""]

    # 关键日期
    fm += [
        "## 关键日期",
        f"- 设计方案评审：{_fmt_dt(ticket.design_reviewed_date) if hasattr(ticket, 'design_reviewed_date') else '—'}",
        f"- 开发完成：{_fmt_dt(ticket.dev_completed_date) if hasattr(ticket, 'dev_completed_date') else '—'}",
        f"- 测试完成：{_fmt_dt(ticket.test_completed_date) if hasattr(ticket, 'test_completed_date') else '—'}",
        f"- 上线：{_fmt_dt(ticket.go_live_date) if hasattr(ticket, 'go_live_date') else '—'}",
        "",
    ]

    # 交付物
    if deliverables:
        fm += ["## 交付物", ""]
        for d in deliverables:
            type_label = {
                "operation_manual": "操作手册",
                "interface_doc": "接口文档",
                "test_case": "测试用例",
                "release_note": "发布说明",
                "other": "其他",
            }.get(d.deliverable_type, d.deliverable_type)
            fm.append(f"- **{type_label}**：{d.file_name}")
            if d.obsidian_path:
                fm.append(f"  - 路径：`{d.obsidian_path}`")
            if d.note:
                fm.append(f"  - 备注：{d.note}")
        fm.append("")
    else:
        fm += ["## 交付物", "（暂无）", ""]

    # 状态变更日志
    if logs:
        fm += ["## 状态变更记录", ""]
        for log in logs:
            fm.append(f"- {_fmt_dt(log.created_at)}：{log.from_status} → {log.to_status}" + (f"（{log.note}）" if log.note else ""))
        fm.append("")

    # 关联
    fm += [
        "## 关联",
        f"- 需求：[[{ticket.req_id}]]" + (f"（{req_name}）" if req_name else ""),
        "",
    ]

    return "\n".join(fm)


def sediment_dev_ticket(db, ticket_id: int) -> Dict:
    """把开发工单沉淀为知识条目，返回 {obsidian_path, knowledge_item_id, item_id, created}。"""
    ticket = db.query(PmwbDevTicket).filter(PmwbDevTicket.id == ticket_id).first()
    if not ticket:
        raise NotFoundException(f"开发工单不存在：id={ticket_id}")

    # 幂等
    existing = _find_existing_index(db, "ticket", str(ticket_id))
    if existing:
        return {
            "obsidian_path": existing.obsidian_path,
            "knowledge_item_id": existing.id,
            "item_id": existing.item_id,
            "created": False,
        }

    # 聚合关联数据
    deliverables = db.query(PmwbDevDeliverable).filter(PmwbDevDeliverable.ticket_id == ticket_id).all()
    logs = db.query(PmwbDevTicketLog).filter(PmwbDevTicketLog.ticket_id == ticket_id).order_by(PmwbDevTicketLog.created_at.desc()).limit(20).all()
    email = db.query(SentEmail).filter(SentEmail.req_id == ticket.req_id).first()

    filename = f"{sanitize_filename(ticket.ticket_no)}_{sanitize_filename(ticket.system_name)}.md"
    rel_path = f"{DEV_TICKET_SEDIMENT_DIR}/{filename}"

    if not read_markdown(rel_path):
        write_markdown(rel_path, _build_dev_ticket_markdown(ticket, deliverables, logs, email))

    domain_code = getattr(ticket, "domain_code", None)
    summary = (ticket.description or f"{ticket.ticket_no} - {ticket.system_name}")[:200]
    item = knowledge_item_service.create(
        db,
        {
            "item_id": _gen_item_id(),
            "title": f"{ticket.ticket_no} - {ticket.system_name}",
            "category": "requirement",
            "sub_category": "开发工单",
            "tags": f"开发工单,{ticket.system_name or '通用'}",
            "obsidian_path": rel_path,
            "source_type": "ticket",
            "source_id": str(ticket_id),
            "domain_code": domain_code,
            "summary": summary,
        },
    )
    # 回填 deliverable_path
    ticket.deliverable_path = rel_path
    db.commit()
    return {
        "obsidian_path": rel_path,
        "knowledge_item_id": item.id,
        "item_id": item.item_id,
        "created": True,
    }
