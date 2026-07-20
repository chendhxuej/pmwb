from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from db.base import Base


class PmwbRequirementExt(Base):
    """需求管理扩展表。"""

    __tablename__ = "pmwb_requirement_ext"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    req_id = Column(String(64), nullable=False, unique=True, comment="需求编号，对应 sent_emails.req_id")
    status = Column(
        String(64),
        default="proposed",
        comment="个人跟踪状态：proposed/accepted/dev/closed/paused",
    )
    tags = Column(String(512), comment="个人标签，逗号分隔")
    personal_note = Column(Text, comment="个人备注")
    priority = Column(String(64), default="P2", comment="个人优先级：P0/P1/P2/P3/集团需求/紧急需求等")
    owner_note = Column(Text, comment="负责人备忘")
    version_required_date = Column(Date, comment="版本要求(需求管理要求的上线时间)")
    req_name = Column(String(500), comment="需求名称（可编辑覆盖）")
    background = Column(Text, comment="需求背景（可编辑覆盖）")
    description = Column(Text, comment="需求描述（可编辑覆盖）")
    clarification = Column(Text, comment="澄清内容（可编辑覆盖）")
    system_name = Column(String(255), comment="涉及系统（可编辑覆盖）")
    sa_name = Column(String(255), comment="SA（可编辑覆盖）")
    eval_seeded = Column(Integer, default=0, comment="团队评估是否已从 sent_emails 播种(避免删除后复活)")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )

    __table_args__ = (
        Index("idx_req_status", "status"),
        {"comment": "需求管理扩展表"},
    )


class PmwbUserStory(Base):
    """需求用户故事表。

    与需求编号（req_id）唯一关联：同一需求可有多条用户故事，按 seq 排序。
    """

    __tablename__ = "pmwb_user_story"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    req_id = Column(String(64), nullable=False, comment="需求编号")
    seq = Column(Integer, default=1, comment="故事序号")
    title = Column(String(500), comment="故事标题")
    desc = Column(Text, comment="故事描述")
    scene = Column(Text, comment="故事场景")
    acceptance = Column(Text, comment="验收标准(JSON数组)")
    finalized = Column(Integer, default=0, comment="是否已定稿(0:草稿 1:定稿)")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )

    __table_args__ = (
        UniqueConstraint("req_id", "seq", name="uk_user_story_req_seq"),
        Index("idx_user_story_req_id", "req_id"),
        {"comment": "需求用户故事表"},
    )


class PmwbDevTicket(Base):
    """开发工单主表。"""

    __tablename__ = "pmwb_dev_ticket"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    ticket_no = Column(String(64), nullable=False, comment="开发工单编号")
    req_id = Column(String(64), nullable=False, comment="关联需求编号")
    system_name = Column(String(128), nullable=False, comment="涉及系统")
    dev_team = Column(String(64), comment="开发团队/厂商")
    developer = Column(String(64), comment="开发负责人")
    dev_contact = Column(String(128), comment="开发联系方式")
    created_at = Column(DateTime, default=datetime.utcnow, comment="工单创建时间")
    design_reviewed_date = Column(Date, comment="设计方案评审日期")
    dev_completed_date = Column(Date, comment="实际完成开发日期")
    test_completed_date = Column(Date, comment="测试完成日期")
    go_live_date = Column(Date, comment="实际上线日期")
    archived_date = Column(Date, comment="归档日期")
    status = Column(
        Enum(
            "created",
            "design_reviewed",
            "dev_completed",
            "test_completed",
            "live",
            "archived",
        ),
        default="created",
        comment="当前状态",
    )
    progress = Column(Integer, default=0, comment="进度百分比 0-100")
    description = Column(Text, comment="工单描述/开发内容")
    risk_note = Column(Text, comment="风险/延期原因")
    deliverable_path = Column(String(512), comment="Obsidian交付物归档路径")
    is_overdue = Column(Integer, default=0, comment="是否超期")
    priority = Column(Enum("P0", "P1", "P2", "P3"), default="P2", comment="优先级")
    created_by = Column(String(64), comment="创建人")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )

    __table_args__ = (
        UniqueConstraint("ticket_no", "system_name", name="uk_ticket_system"),
        Index("idx_dev_req_id", "req_id"),
        Index("idx_dev_status", "status"),
        {"comment": "开发工单表"},
    )


class PmwbDevDeliverable(Base):
    """开发交付物表。"""

    __tablename__ = "pmwb_dev_deliverable"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    ticket_id = Column(Integer, ForeignKey("pmwb_dev_ticket.id"), nullable=False, comment="关联工单ID")
    deliverable_type = Column(
        Enum("operation_manual", "interface_doc", "test_case", "release_note", "other"),
        default="other",
        comment="交付物类型",
    )
    file_name = Column(String(255), nullable=False, comment="文件名")
    original_name = Column(String(255), comment="原始文件名")
    file_size = Column(Integer, comment="文件大小(字节)")
    file_type = Column(String(64), comment="文件MIME类型")
    obsidian_path = Column(String(512), comment="Obsidian归档完整路径")
    local_path = Column(String(512), comment="本地备份路径")
    source = Column(String(32), default="upload", comment="来源 (plugin/upload)")
    source_url = Column(String(1024), comment="来源URL")
    note = Column(Text, comment="备注")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    __table_args__ = (
        Index("idx_deliverable_ticket_id", "ticket_id"),
        {"comment": "开发交付物表"},
    )


class PmwbDevTicketLog(Base):
    """开发工单状态变更日志。"""

    __tablename__ = "pmwb_dev_ticket_log"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    ticket_id = Column(Integer, ForeignKey("pmwb_dev_ticket.id"), nullable=False, comment="关联工单ID")
    from_status = Column(String(32), comment="变更前状态")
    to_status = Column(String(32), comment="变更后状态")
    operator = Column(String(64), comment="操作人")
    note = Column(Text, comment="变更原因/备注")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    __table_args__ = (
        Index("idx_log_ticket_id", "ticket_id"),
        {"comment": "开发工单状态变更日志"},
    )


class PmwbTodo(Base):
    """待办任务表。"""

    __tablename__ = "pmwb_todo"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    title = Column(String(255), nullable=False, comment="待办标题")
    content = Column(Text, comment="待办内容")
    category = Column(
        String(64),
        default="other",
        comment="分类：requirement/ticket/operation/meeting/study/other",
    )
    priority = Column(Enum("P0", "P1", "P2", "P3"), default="P2", comment="优先级")
    status = Column(
        Enum("todo", "in_progress", "done", "cancelled"),
        default="todo",
        comment="状态",
    )
    due_date = Column(Date, comment="截止日期")
    due_time = Column(String(8), comment="截止时间")
    remind_at = Column(DateTime, comment="提醒时间")
    repeat_type = Column(
        Enum("none", "daily", "weekly", "monthly"),
        default="none",
        comment="重复类型",
    )
    related_type = Column(
        String(64),
        comment="关联对象类型：requirement/ticket/operation/meeting",
    )
    related_id = Column(String(64), comment="关联对象ID")
    source = Column(String(64), default="manual", comment="来源：manual/meeting/plugin")
    completed_at = Column(DateTime, comment="完成时间")
    is_overdue = Column(Integer, default=0, comment="是否超期")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )

    __table_args__ = (
        Index("idx_todo_status", "status"),
        Index("idx_todo_due_date", "due_date"),
        Index("idx_todo_related", "related_type", "related_id"),
        {"comment": "待办任务表"},
    )


class PmwbOperationIssue(Base):
    """业务运营问题表。"""

    __tablename__ = "pmwb_operation_issue"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    issue_no = Column(String(64), nullable=False, unique=True, comment="工单编号")
    title = Column(String(255), nullable=False, comment="工单标题")
    category = Column(
        Enum("bug", "data", "prod", "task", "complaint"),
        default="prod",
        comment="工单大类：BUG管理/数据异常管理/生产问题分析/临时交办任务/热点投诉",
    )
    issue_type = Column(
        Enum("bug", "data_abnormal", "topic_analysis", "spot_event", "temp_task", "other"),
        default="other",
        comment="问题子类(细分类型): BUG/数据异常/专题分析/投点事件/临时任务/其他",
    )
    status = Column(
        Enum("pending", "processing", "verify", "resolved", "closed", "suspended"),
        default="pending",
        comment="状态",
    )
    source = Column(String(64), default="manual", comment="来源")
    discovery_date = Column(DateTime, comment="发现时间")
    resolve_date = Column(DateTime, comment="解决时间")
    handler = Column(String(512), comment="处理人(多选,逗号分隔)")
    situation_desc = Column(Text, comment="情况说明")
    impact_level = Column(Enum("P0", "P1", "P2", "P3"), default="P2", comment="影响等级")
    root_cause = Column(Text, comment="根因分析")
    solution = Column(Text, comment="解决方案")
    related_req_id = Column(String(64), comment="关联需求编号")
    related_ticket_no = Column(String(64), comment="关联开发工单编号")
    related_system = Column(String(128), comment="关联系统")
    obsidian_path = Column(String(512), comment="沉淀知识条目路径")
    is_overdue = Column(Integer, default=0, comment="是否超期")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )

    __table_args__ = (
        Index("idx_issue_status", "status"),
        Index("idx_issue_type", "issue_type"),
        Index("idx_issue_category", "category"),
        Index("idx_issue_related_req", "related_req_id"),
        {"comment": "业务运营工单表"},
    )


class PmwbMeeting(Base):
    """会议表。"""

    __tablename__ = "pmwb_meeting"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    meeting_id = Column(String(64), nullable=False, unique=True, comment="会议编号")
    title = Column(String(255), nullable=False, comment="会议主题")
    meeting_type = Column(
        Enum("requirement_review", "project_weekly", "troubleshooting", "training", "other"),
        default="other",
        comment="会议类型",
    )
    start_time = Column(DateTime, comment="开始时间")
    end_time = Column(DateTime, comment="结束时间")
    location = Column(String(255), comment="会议地点/线上链接")
    host = Column(String(64), comment="主持人/组织者")
    convener = Column(String(64), comment="召集人")
    attendee_notes = Column(Text, comment="参会注意点（会议通知补充事项）")
    summary = Column(Text, comment="会议纪要摘要")
    obsidian_path = Column(String(512), comment="Obsidian 纪要路径")
    related_req_id = Column(String(64), comment="关联需求编号")
    related_ticket_no = Column(String(64), comment="关联开发工单编号")
    status = Column(Enum("planned", "held", "cancelled"), default="planned", comment="状态")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )

    attendees = relationship("PmwbMeetingAttendee", backref="meeting", lazy="selectin", cascade="all, delete-orphan")
    agendas = relationship("PmwbMeetingAgenda", backref="meeting", lazy="selectin", cascade="all, delete-orphan", order_by="PmwbMeetingAgenda.seq")
    actions = relationship("PmwbMeetingAction", backref="meeting", lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_meeting_start_time", "start_time"),
        Index("idx_meeting_related_req", "related_req_id"),
        {"comment": "会议表"},
    )


class PmwbMeetingAgenda(Base):
    """会议议题表（每个议题记录商讨结论与分工说明）。"""

    __tablename__ = "pmwb_meeting_agenda"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    meeting_id = Column(Integer, ForeignKey("pmwb_meeting.id"), nullable=False, comment="关联会议ID")
    seq = Column(Integer, default=1, comment="议题序号（用于排序）")
    topic = Column(String(255), nullable=False, comment="议题标题")
    conclusion = Column(Text, comment="商讨结论")
    division = Column(Text, comment="分工说明")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )

    __table_args__ = (
        Index("idx_agenda_meeting_id", "meeting_id"),
        {"comment": "会议议题表"},
    )


class PmwbMeetingAttendee(Base):
    """会议参会人表。"""

    __tablename__ = "pmwb_meeting_attendee"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    meeting_id = Column(Integer, ForeignKey("pmwb_meeting.id"), nullable=False, comment="关联会议ID")
    name = Column(String(64), nullable=False, comment="参会人姓名")
    email = Column(String(128), comment="邮箱")
    dept = Column(String(128), comment="部门")
    is_required = Column(Integer, default=1, comment="是否必须参加")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    __table_args__ = ({"comment": "会议参会人表"},)


class PmwbMeetingAction(Base):
    """会议行动项表。"""

    __tablename__ = "pmwb_meeting_action"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    meeting_id = Column(Integer, ForeignKey("pmwb_meeting.id"), nullable=False, comment="关联会议ID")
    content = Column(Text, nullable=False, comment="行动项内容")
    owner = Column(String(64), comment="负责人")
    due_date = Column(Date, comment="截止日期")
    status = Column(Enum("pending", "done", "cancelled"), default="pending", comment="状态")
    category = Column(
        String(64),
        comment="待办分类（对应 pmwb_todo.category）：requirement/ticket/operation/meeting/study/other",
    )
    template = Column(String(128), comment="Obsidian 待办模板名（仅元数据标签，如 个人普通待办模板）")
    related_todo_id = Column(Integer, comment="关联 pmwb_todo.id")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )

    __table_args__ = (
        Index("idx_action_meeting_id", "meeting_id"),
        {"comment": "会议行动项表"},
    )


class PmwbKnowledgeItem(Base):
    """知识库条目索引表。"""

    __tablename__ = "pmwb_knowledge_item"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    item_id = Column(String(64), nullable=False, unique=True, comment="知识条目编号")
    title = Column(String(255), nullable=False, comment="标题")
    category = Column(
        String(64),
        nullable=False,
        comment="分类：product/operation/requirement/meeting/personal/study",
    )
    sub_category = Column(String(128), comment="子分类")
    tags = Column(String(512), comment="标签，逗号分隔")
    obsidian_path = Column(String(512), nullable=False, comment="Obsidian 文件路径")
    source_type = Column(
        String(64),
        comment="来源类型：requirement/ticket/operation/meeting/manual",
    )
    source_id = Column(String(64), comment="来源对象ID")
    summary = Column(Text, comment="摘要")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )

    __table_args__ = (
        Index("idx_knowledge_category", "category"),
        Index("idx_knowledge_source", "source_type", "source_id"),
        {"comment": "知识库条目索引表"},
    )


class PmwbRequirementEvaluation(Base):
    """需求团队评估记录表（可自由增删改的清单）。

    首次打开某需求时，会从只读来源 sent_emails 自动播种出可编辑的评估记录；
    之后产品经理可新增/修改/删除任意一条。sent_email_id 仅用于溯源，
    手动新增的记录 sent_email_id 为 NULL。
    """

    __tablename__ = "pmwb_requirement_evaluation"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID（评估记录自身标识）")
    sent_email_id = Column(
        Integer, nullable=True, unique=True, comment="溯源：关联 sent_emails.id；手动新增记录为 NULL"
    )
    req_id = Column(String(255), comment="需求编号，冗余便于查询")
    req_name = Column(String(255), comment="需求名称（冗余，便于展示/催办）")
    proposer = Column(String(64), comment="提出人（冗余，便于催办）")
    send_datetime = Column(String(255), comment="邮件发送时间（溯源展示用）")
    sa_name = Column(String(64), comment="评估SA/团队负责人")
    system_name = Column(String(255), comment="负责系统")
    workload = Column(Numeric(10, 2), comment="工作量评估(人天)")
    review_workload = Column(Numeric(10, 2), comment="复核工作量(人天)")
    opinion = Column(Text, comment="评估意见登记")
    dev_ticket_no = Column(String(255), comment="开发单号")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )

    __table_args__ = (
        Index("idx_eval_req_id", "req_id"),
        {"comment": "需求团队评估扩展表"},
    )


class SentEmail(Base):
    """已发送需求邮件记录表（只读/关联）。"""

    __tablename__ = "sent_emails"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    req_id = Column(String(255), comment="需求编号")
    req_name = Column(String(500), comment="需求名称")
    proposer = Column(String(255), comment="提出人")
    propose_time = Column(String(255), comment="提出时间")
    background = Column(Text, comment="需求背景及目标")
    description = Column(Text, comment="需求描述")
    clarification = Column(Text, comment="需求澄清")
    system_name = Column(String(255), comment="系统")
    sa_name = Column(String(255), comment="SA")
    send_datetime = Column(String(64), comment="邮件发送日期")
    created_at = Column(DateTime, default=datetime.utcnow, comment="写入时间")
    workload = Column(Numeric(10, 2), comment="工作量")
    is_involved = Column(Integer, default=1, comment="是否涉及开发(0:否,1:是)")
    dev_ticket_no = Column(String(255), comment="开发单号")
    involve_dev = Column(String(10), default="是", comment="涉及开发")

    __table_args__ = ({"comment": "已发送邮件记录"},)


class EmailRecord(Base):
    """统一邮件发送记录表（已有表 email_records）。"""

    __tablename__ = "email_records"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    req_id = Column(String(255), comment="需求编号")
    req_name = Column(String(500), comment="需求名称")
    email_type = Column(String(255), comment="邮件类型")
    recipient = Column(String(255), comment="收件人邮箱")
    recipient_name = Column(String(255), comment="收件人姓名")
    subject = Column(String(500), comment="邮件主题")
    content = Column(Text, comment="邮件正文")
    send_status = Column(String(255), comment="发送状态")
    error_msg = Column(Text, comment="错误信息")
    source = Column(String(255), comment="来源系统")
    sender = Column(String(255), comment="发送人")
    created_at = Column(DateTime, default=datetime.utcnow, comment="发送时间")

    __table_args__ = (
        Index("idx_email_record_req_id", "req_id"),
        {"comment": "邮件发送记录"},
    )


class SaInfo(Base):
    """SA 收件人信息表（原 2525 中继的 sa_info，现由 PMWB 统一托管）。"""

    __tablename__ = "sa_info"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    sa_name = Column(String(255), nullable=False, comment="SA姓名")
    system_name = Column(String(255), default=None, comment="系统名称")
    email = Column(String(255), nullable=False, comment="邮箱")
    wechat_nickname = Column(String(255), default=None, comment="微信昵称")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    __table_args__ = (
        Index("uk_sa_info_system", "sa_name", "system_name"),
        {"comment": "SA收件人信息表"},
    )
