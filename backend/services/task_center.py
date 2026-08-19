"""任务中心 Service：实时聚合全系统六类待办任务 + 邮件通知/催办。

聚合方式为实时查询（各来源 collector 内存映射为统一 TaskItem），不落快照表。
旧 /reminders 接口与 ReminderService 保持不动，本服务独立并存。
"""

import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.exceptions import ValidationException
from db.models import (
    EmailRecord,
    PmwbDevTicket,
    PmwbKeyWork,
    PmwbKeyWorkMemberTask,
    PmwbKeyWorkMilestone,
    PmwbMeeting,
    PmwbMeetingAction,
    PmwbOperationIssue,
    PmwbTodo,
    SentEmail,
)
from schemas.task_center import (
    SOURCE_LABELS,
    STATUS_LABELS,
    TASK_SOURCES,
    TaskItem,
    TaskRef,
    TaskSendRequest,
    TaskStats,
)
from services.mail_dispatch import _render_mail, dispatch_email
from utils.dateflags import flag_due_date
from utils.email import EmailCenterClient
from utils.master_service import master_service_client
from utils.validators import split_and_validate_emails

logger = logging.getLogger("pmwb.task_center")

DUE_SOON_DAYS = 3

# 各来源原始状态 → 统一状态映射
_STATUS_MAP: Dict[str, Dict[str, str]] = {
    "todo": {
        "todo": "pending",
        "in_progress": "in_progress",
        "done": "done",
        "cancelled": "blocked",
    },
    "operation_issue": {
        "pending": "pending",
        "processing": "in_progress",
        "verify": "in_progress",
        "resolved": "in_progress",
        "closed": "done",
        "suspended": "blocked",
    },
    "dev_ticket": {
        "created": "pending",
        "design_reviewed": "in_progress",
        "dev_completed": "in_progress",
        "test_completed": "in_progress",
        "live": "done",
        "archived": "done",
    },
    "key_work_task": {
        "todo": "pending",
        "in_progress": "in_progress",
        "done": "done",
        "cancelled": "blocked",
    },
    "key_work_milestone": {
        "pending": "pending",
        "in_progress": "in_progress",
        "done": "done",
        "delayed": "blocked",
    },
    "key_work_main": {
        "planning": "pending",
        "in_progress": "in_progress",
        "completed": "done",
        "paused": "blocked",
        "cancelled": "blocked",
    },
}


def _map_meeting_action_status(raw: str) -> str:
    """会议行动项状态为自由串，做容错映射。"""
    s = (raw or "").strip().lower()
    if not s or s == "pending" or "待" in s:
        return "pending"
    if s in ("done", "completed", "closed") or "完成" in s or "关闭" in s:
        return "done"
    if s == "in_progress" or "进行" in s or "处理" in s:
        return "in_progress"
    if "取消" in s or "挂起" in s or "暂停" in s:
        return "blocked"
    return "pending"


def _flag_dates(due: Optional[date], status: str) -> Dict[str, bool]:
    """计算超期/临期标记（终态不算），复用共享日期工具。"""
    return flag_due_date(due, status, due_soon_days=DUE_SOON_DAYS)


class TaskCenterService:
    """任务中心聚合服务。"""

    def __init__(self):
        self.email_client = EmailCenterClient()

    # ------------------------------------------------------------------
    # collectors：每个来源一个采集器，返回 List[TaskItem]
    # ------------------------------------------------------------------

    def collect_todo(self, db: Session) -> List[TaskItem]:
        rows = db.query(PmwbTodo).all()
        items: List[TaskItem] = []
        for r in rows:
            status = _STATUS_MAP["todo"].get(r.status or "todo", "pending")
            flags = _flag_dates(r.due_date, status)
            items.append(TaskItem(
                task_id=f"todo:{r.id}",
                source="todo",
                source_label=SOURCE_LABELS["todo"],
                source_id=str(r.id),
                title=r.title or "",
                status=status,
                status_label=STATUS_LABELS[status],
                raw_status=r.status or "",
                owner="我",
                priority=r.priority,
                due_date=r.due_date,
                created_at=r.created_at.date() if r.created_at else None,
                source_url=f"/todo?id={r.id}",
                detail={
                    "分类": r.category,
                    "内容": (r.content or ""),
                    "来源": r.source,
                    "截止时间": r.due_time,
                },
                **flags,
            ))
        return items

    def collect_operation_issue(self, db: Session) -> List[TaskItem]:
        rows = db.query(PmwbOperationIssue).all()
        items: List[TaskItem] = []
        for r in rows:
            status = _STATUS_MAP["operation_issue"].get(r.status or "pending", "pending")
            due = r.discovery_date.date() if r.discovery_date else None
            # 运营问题无截止日期字段，超期以表内 is_overdue 为准
            flags = {
                "is_overdue": bool(r.is_overdue) and status not in ("done", "blocked"),
                "is_due_soon": False,
            }
            items.append(TaskItem(
                task_id=f"operation_issue:{r.id}",
                source="operation_issue",
                source_label=SOURCE_LABELS["operation_issue"],
                source_id=str(r.id),
                title=f"[{r.issue_no}] {r.title or ''}",
                status=status,
                status_label=STATUS_LABELS[status],
                raw_status=r.status or "",
                owner=r.handler or "",
                priority=r.impact_level,
                due_date=due,
                created_at=r.created_at.date() if r.created_at else None,
                source_url=f"/operation?issueId={r.id}",
                detail={
                    "工单编号": r.issue_no,
                    "大类": r.category,
                    "子类": r.issue_type,
                    "关联系统": r.related_system,
                    "关联需求": r.related_req_id,
                    "情况说明": (r.situation_desc or ""),
                },
                **flags,
            ))
        return items

    def collect_dev_ticket(self, db: Session) -> List[TaskItem]:
        rows = db.query(PmwbDevTicket).all()
        items: List[TaskItem] = []
        for r in rows:
            status = _STATUS_MAP["dev_ticket"].get(r.status or "created", "pending")
            flags = {
                "is_overdue": bool(r.is_overdue) and status != "done",
                "is_due_soon": False,
            }
            title = (r.description or "").strip().splitlines()[0] if r.description else ""
            items.append(TaskItem(
                task_id=f"dev_ticket:{r.id}",
                source="dev_ticket",
                source_label=SOURCE_LABELS["dev_ticket"],
                source_id=str(r.id),
                title=f"[{r.ticket_no}] {title}",
                status=status,
                status_label=STATUS_LABELS[status],
                raw_status=r.status or "",
                owner=r.developer or "",
                priority=r.priority,
                due_date=r.go_live_date,  # 开发工单计划完成=实际上线日期
                created_at=r.created_at.date() if r.created_at else None,
                source_url=f"/requirement-delivery?ticket={r.ticket_no}",
                detail={
                    "工单编号": r.ticket_no,
                    "关联需求": r.req_id,
                    "涉及系统": r.system_name,
                    "开发团队": r.dev_team,
                    "进度": f"{r.progress or 0}%",
                    "风险说明": (r.risk_note or ""),
                },
                **flags,
            ))
        return items

    def collect_meeting_action(self, db: Session) -> List[TaskItem]:
        rows = (
            db.query(PmwbMeetingAction, PmwbMeeting.title)
            .outerjoin(PmwbMeeting, PmwbMeetingAction.meeting_id == PmwbMeeting.id)
            .all()
        )
        items: List[TaskItem] = []
        for r, meeting_title in rows:
            status = _map_meeting_action_status(r.status)
            flags = _flag_dates(r.due_date, status)
            items.append(TaskItem(
                task_id=f"meeting_action:{r.id}",
                source="meeting_action",
                source_label=SOURCE_LABELS["meeting_action"],
                source_id=str(r.id),
                title=(r.content or ""),
                status=status,
                status_label=STATUS_LABELS[status],
                raw_status=r.status or "",
                owner=r.owner or "",
                priority=None,
                due_date=r.due_date,
                created_at=r.created_at.date() if r.created_at else None,
                source_url=f"/meeting?actionId={r.id}",
                synced_to_todo=bool(r.related_todo_id),
                detail={
                    "所属会议": meeting_title or f"会议#{r.meeting_id}",
                    "行动项": (r.content or ""),
                    "分类": r.category,
                },
                **flags,
            ))
        return items

    def collect_key_work(self, db: Session) -> List[TaskItem]:
        items: List[TaskItem] = []
        # 成员待办
        tasks = (
            db.query(PmwbKeyWorkMemberTask, PmwbKeyWork.title)
            .outerjoin(PmwbKeyWork, PmwbKeyWorkMemberTask.key_work_id == PmwbKeyWork.id)
            .all()
        )
        for r, kw_title in tasks:
            status = _STATUS_MAP["key_work_task"].get(r.status or "todo", "pending")
            flags = _flag_dates(r.due_date, status)
            items.append(TaskItem(
                task_id=f"key_work:task-{r.id}",
                source="key_work",
                source_label=SOURCE_LABELS["key_work"],
                source_id=f"task-{r.id}",
                title=r.title or "",
                status=status,
                status_label=STATUS_LABELS[status],
                raw_status=r.status or "",
                owner=r.assignee or "",
                priority=None,
                due_date=r.due_date,
                created_at=r.created_at.date() if r.created_at else None,
                source_url=f"/key-works?id=task-{r.id}",
                detail={
                    "类型": "成员待办",
                    "所属重点工作": kw_title,
                    "备注": (r.note or ""),
                },
                **flags,
            ))
        # 里程碑
        milestones = (
            db.query(PmwbKeyWorkMilestone, PmwbKeyWork.title, PmwbKeyWork.owner)
            .outerjoin(PmwbKeyWork, PmwbKeyWorkMilestone.key_work_id == PmwbKeyWork.id)
            .all()
        )
        for r, kw_title, kw_owner in milestones:
            status = _STATUS_MAP["key_work_milestone"].get(r.status or "pending", "pending")
            flags = _flag_dates(r.due_date, status)
            items.append(TaskItem(
                task_id=f"key_work:milestone-{r.id}",
                source="key_work",
                source_label=SOURCE_LABELS["key_work"],
                source_id=f"milestone-{r.id}",
                title=f"[里程碑] {r.name or ''}",
                status=status,
                status_label=STATUS_LABELS[status],
                raw_status=r.status or "",
                owner=kw_owner or "",
                priority=None,
                due_date=r.due_date,
                created_at=r.created_at.date() if r.created_at else None,
                source_url=f"/key-works?id=milestone-{r.id}",
                detail={
                    "类型": "里程碑",
                    "所属重点工作": kw_title,
                    "说明": (r.note or ""),
                },
                **flags,
            ))
        return items

    def collect_requirement_urge(self, db: Session) -> List[TaskItem]:
        """待催办需求（团队评估维度）：以 pmwb_requirement_evaluation 为准。

        判据（2026-07 修正）：只看团队评估行中「工作量（人天）」为空的记录，
        每条空工作量行归属其自身的 SA 负责人（按 需求+SA 去重）；
        不再要求「复核工作量未填 + 无开发单号」同时成立。
        需求已关闭/暂停不催办。
        """
        from db.models import PmwbRequirementEvaluation, PmwbRequirementExt

        # 需求宇宙 = sent_emails 去重后的 req_id（与需求模块口径一致，排除孤儿 ext 脏数据）
        sent_req_ids = {
            row[0] for row in db.query(SentEmail.req_id).distinct().all() if row[0]
        }
        # 有效状态：ext.status 非空用之，否则兜底为 'proposed'（与需求模块/前端渲染完全对齐）
        ext_status = {
            r[0]: (r[1] if r[1] else "proposed")
            for r in db.query(PmwbRequirementExt.req_id, PmwbRequirementExt.status).all()
            if r[0] in sent_req_ids
        }
        # 需求级终态集合（已关闭/暂停的不催办）
        closed_ids = {
            rid
            for rid in sent_req_ids
            if ext_status.get(rid, "proposed") in ("closed", "paused")
        }

        rows = (
            db.query(
                PmwbRequirementEvaluation.req_id,
                PmwbRequirementEvaluation.req_name,
                PmwbRequirementEvaluation.proposer,
                PmwbRequirementEvaluation.sa_name,
                PmwbRequirementEvaluation.system_name,
                PmwbRequirementEvaluation.dev_ticket_no,
            )
            .filter(func.coalesce(PmwbRequirementEvaluation.workload, 0) == 0)
            .order_by(
                PmwbRequirementEvaluation.req_id,
                PmwbRequirementEvaluation.sa_name,
            )
            .all()
        )

        # 需求描述映射（优先 ext，回退 sent_email），用于催办正文
        req_ids = [r.req_id for r in rows if r.req_id not in closed_ids]
        desc_map: Dict[str, Optional[str]] = {}
        if req_ids:
            ext_rows = (
                db.query(PmwbRequirementExt.req_id, PmwbRequirementExt.description)
                .filter(PmwbRequirementExt.req_id.in_(req_ids))
                .all()
            )
            for rid, d in ext_rows:
                if d:
                    desc_map[rid] = d
            still_missing = [rid for rid in req_ids if rid not in desc_map]
            if still_missing:
                sent_rows = (
                    db.query(SentEmail.req_id, SentEmail.description)
                    .filter(SentEmail.req_id.in_(still_missing))
                    .all()
                )
                for rid, d in sent_rows:
                    if d and rid not in desc_map:
                        desc_map[rid] = d

        items: List[TaskItem] = []
        seen = set()
        for r in rows:
            if r.req_id in closed_ids:
                continue
            owner = (r.sa_name or "").strip() or "未分配"
            key = (r.req_id, owner)
            if key in seen:
                continue
            seen.add(key)
            system = (r.system_name or "").strip() or "未指定"
            desc = desc_map.get(r.req_id) or ""
            items.append(TaskItem(
                task_id=f"requirement_urge:{r.req_id}:{owner}",
                source="requirement_urge",
                source_label=SOURCE_LABELS["requirement_urge"],
                source_id=f"{r.req_id}:{owner}",
                title=f"[{r.req_id}] {r.req_name or ''}",
                status="pending",
                status_label=STATUS_LABELS["pending"],
                raw_status="待团队评估",
                owner=owner,
                priority=None,
                due_date=None,
                created_at=None,
                source_url=f"/requirement-delivery?req={r.req_id}&sa={r.sa_name}",
                detail={
                    "需求编号": r.req_id,
                    "提出人": r.proposer,
                    "涉及系统": system,
                    "评估团队(SA)": owner,
                    "团队评估状态": "工作量未登记",
                    "需求描述": desc,
                },
                is_overdue=False,
                is_due_soon=False,
            ))
        return items

    # ------------------------------------------------------------------
    # 聚合查询
    # ------------------------------------------------------------------

    _COLLECTORS = {
        "todo": "collect_todo",
        "operation_issue": "collect_operation_issue",
        "dev_ticket": "collect_dev_ticket",
        "meeting_action": "collect_meeting_action",
        "key_work": "collect_key_work",
        "requirement_urge": "collect_requirement_urge",
    }

    def _collect(self, db: Session, sources: Optional[List[str]] = None) -> List[TaskItem]:
        targets = sources or TASK_SOURCES
        all_items: List[TaskItem] = []
        for src in targets:
            method = self._COLLECTORS.get(src)
            if not method:
                continue
            try:
                all_items.extend(getattr(self, method)(db))
            except Exception as exc:  # noqa: BLE001
                logger.warning("任务中心来源 %s 采集失败: %s", src, exc)
        return all_items

    def get_tasks(
        self,
        db: Session,
        source: Optional[str] = None,
        status: Optional[str] = None,
        only_overdue: bool = False,
        include_done: bool = False,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """统一任务列表（筛选 + 分页）。"""
        sources = [source] if source else None
        items = self._collect(db, sources)
        if not include_done:
            items = [t for t in items if t.status not in ("done", "blocked")]
        if status:
            items = [t for t in items if t.status == status]
        if only_overdue:
            items = [t for t in items if t.is_overdue]
        if keyword:
            kw = keyword.strip().lower()
            items = [
                t for t in items
                if kw in t.title.lower() or kw in (t.owner or "").lower()
                or kw in str(t.detail).lower()
            ]
        # 排序：默认按创建时间倒序（无创建时间排最后）；超期/临期仍由高亮与"只看超期"筛选突出
        items.sort(key=lambda t: t.created_at or date.min, reverse=True)
        total = len(items)
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        start = (page - 1) * page_size
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items[start:start + page_size],
        }

    def get_stats(self, db: Session) -> TaskStats:
        """统计卡：总待办/超期/临期/各来源/各状态计数（不含终态）。"""
        items = [t for t in self._collect(db) if t.status not in ("done", "blocked")]
        by_source: Dict[str, int] = {s: 0 for s in TASK_SOURCES}
        by_status: Dict[str, int] = {}
        overdue = due_soon = 0
        for t in items:
            by_source[t.source] = by_source.get(t.source, 0) + 1
            by_status[t.status] = by_status.get(t.status, 0) + 1
            if t.is_overdue:
                overdue += 1
            elif t.is_due_soon:
                due_soon += 1
        return TaskStats(
            total=len(items),
            overdue=overdue,
            due_soon=due_soon,
            by_source=by_source,
            by_status=by_status,
        )

    def get_detail(self, db: Session, task_id: str) -> Optional[TaskItem]:
        """任务详情：按复合键定位。"""
        if ":" not in task_id:
            raise ValidationException("task_id 格式应为 source:source_id")
        source = task_id.split(":", 1)[0]
        if source not in TASK_SOURCES:
            raise ValidationException(f"未知任务来源：{source}")
        for t in self._collect(db, [source]):
            if t.task_id == task_id:
                return t
        return None

    # ------------------------------------------------------------------
    # 邮件通知 / 催办
    # ------------------------------------------------------------------

    def resolve_contacts(self, names: List[str]) -> Dict[str, Optional[str]]:
        """按姓名解析收件人邮箱：优先人员中台(8001)，邮件中心通讯录兜底。

        之前只查邮件中心旧通讯录，导致邮箱与人员中台不一致（如旧域名邮箱）。
        现改为以人员中台为唯一权威来源，邮件中心仅作查不到时的兜底。
        """
        result = master_service_client.resolve_staff_emails(names)
        missing = [n for n, e in result.items() if not e]
        if missing:
            fallback = self.email_client.resolve_contact_emails(missing)
            for n in missing:
                if fallback.get(n):
                    result[n] = fallback[n]
        return result

    def _resolve_recipients_for_send(self, raw: Optional[str]) -> tuple[list[str], list[str]]:
        """把收件人串中的姓名解析为邮箱（已是邮箱的保持不变）。

        返回 (resolved_emails, unresolved_names)。与 mail-dispatch/send 的
        _resolve_recipients 对齐，保证任务中心催办也能接受姓名输入。
        """
        if not raw:
            return [], []
        parts = [p.strip() for p in re.split(r"[,;，；\s]+", raw) if p.strip()]
        emails: list[str] = []
        names: list[str] = []
        for p in parts:
            if "@" in p:
                emails.append(p)
            else:
                names.append(p)
        unresolved: list[str] = []
        if names:
            resolved = self.resolve_contacts(names)
            for n in names:
                e = resolved.get(n)
                if e and "@" in e:
                    emails.append(e)
                else:
                    emails.append(n)
                    unresolved.append(n)
        return emails, unresolved

    def build_email_body(self, db: Session, tasks: List[TaskRef], send_type: str) -> str:
        """按工单标题/内容/责任人/完成时间结构化拼装邮件正文（单一模板来源）。

        收件人看到的每一条工单均包含：标题、来源、责任人、完成时间、当前状态、
        工单内容（源模块关键字段摘要），确保「收到邮件即清楚是什么事」。
        """
        # 不同任务来源 detail 中承载「任务描述」的字段名不一，按优先级取其一
        desc_keys = ["需求描述", "情况说明", "行动项", "内容", "说明", "备注", "风险说明"]
        intro = (
            "各位：\n\n以下任务已到跟进节点，麻烦尽快处理并反馈进展，辛苦了！\n"
            if send_type == "urge"
            else "各位：\n\n同步以下任务的当前情况，请知悉。\n"
        )
        blocks: List[str] = []
        for idx, ref in enumerate(tasks, 1):
            item = self.get_detail(db, f"{ref.source}:{ref.source_id}")
            if item is None:
                blocks.append(
                    f"{idx}. [{SOURCE_LABELS.get(ref.source, ref.source)}] （任务已不存在: {ref.source_id}）"
                )
                continue
            due = f"完成时间：{item.due_date}" if item.due_date else "完成时间：未设定"
            overdue = "【已超期】" if item.is_overdue else ("【即将到期】" if item.is_due_soon else "")
            desc = next((item.detail.get(k) for k in desc_keys if item.detail.get(k)), None)
            content = str(desc).strip() if desc else "（无补充说明）"
            blocks.append(
                f"{idx}. {item.title}\n"
                f"   · 来源：{item.source_label}\n"
                f"   · 责任人：{item.owner or '未指定'}\n"
                f"   · {due}{(' ' + overdue) if overdue else ''}\n"
                f"   · 当前状态：{item.status_label}\n"
                f"   · 工单内容：{content}"
            )
        return intro + "—— 待办事项明细 ——\n" + "\n".join(blocks) + "\n\n—— 产品经理工作台（PMWB）"

    def send_notification(self, db: Session, obj_in: TaskSendRequest) -> Dict[str, Any]:
        """发送任务通知/催办邮件，落 email_records（source=task-center）。

        dry_run=True 时仅返回模板渲染正文（用于前端预览，所见即所得）。
        scene 模式（task_center_notify/urge）：3210 模板渲染正文；
        模板变量优先取前端 template_data（tasks HTML 列表），缺失时后端兜底生成文本清单。
        """
        if not obj_in.tasks:
            raise ValidationException("请至少选择一个任务")

        scene = "task_center_urge" if obj_in.send_type == "urge" else "task_center_notify"
        tdata = obj_in.template_data or {}

        # 模板变量：tasks 列表（{{{tasks}}} 透传 HTML）+ sendType；body 承载可编辑正文（模板渲染降级时兜底）
        variables: Dict[str, Any] = {
            "tasks": tdata.get("tasks") or self.build_email_body(db, obj_in.tasks, obj_in.send_type),
            "sendType": tdata.get("sendType") or obj_in.send_type,
            "body": obj_in.body or tdata.get("body") or "",
        }

        # 预览：仅渲染模板，不校验收件人、不发送、不落库
        if obj_in.dry_run:
            rendered = _render_mail(
                scene=scene,
                variables=variables,
                subject=obj_in.subject,
            )
            return {"success": True, "preview": True, "body": rendered["rendered_body"], "subject": rendered["subject"]}

        # 收件人支持「姓名/邮箱」混合输入：先解析姓名→邮箱，再校验格式
        resolved_to, unresolved_to = self._resolve_recipients_for_send(obj_in.to or "")
        resolved_cc, unresolved_cc = self._resolve_recipients_for_send(obj_in.cc or "")

        bad: List[str] = []
        for addr in resolved_to:
            _, invalid = split_and_validate_emails(addr)
            bad.extend(invalid)
        for addr in resolved_cc:
            _, invalid = split_and_validate_emails(addr)
            bad.extend(invalid)
        if bad:
            raise ValidationException(
                "收件人邮箱格式不正确：" + "、".join(bad)
                + "。请填写真实邮箱（可在统一邮件中心通讯录按姓名查询）。"
            )

        # 取首条任务标题作为记录名
        first_title = ""
        for ref in obj_in.tasks:
            item = self.get_detail(db, f"{ref.source}:{ref.source_id}")
            if item and not first_title:
                first_title = item.title
                break

        email_type = "pmwb_task_urge" if obj_in.send_type == "urge" else "pmwb_task_notify"

        result = dispatch_email(
            db=db,
            to=resolved_to,
            cc=resolved_cc or None,
            subject=obj_in.subject,
            scene=scene,
            variables=variables,
            raw_content=obj_in.body,
            email_type=email_type,
            req_id=";".join(f"{t.source}:{t.source_id}" for t in obj_in.tasks)[:64],
            req_name=(first_title or "任务中心邮件")[:255],
            raise_on_error=False,
        )
        return {"success": result.get("success", False), "record_ids": [result.get("record_id")] if result.get("record_id") else [], "message": result.get("message", "")}


task_center_service = TaskCenterService()
