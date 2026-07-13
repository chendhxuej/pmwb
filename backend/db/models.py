from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

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
    priority = Column(Enum("P0", "P1", "P2", "P3"), default="P2", comment="个人优先级")
    owner_note = Column(Text, comment="负责人备忘")
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
    issue_no = Column(String(64), nullable=False, unique=True, comment="问题编号")
    title = Column(String(255), nullable=False, comment="问题标题")
    issue_type = Column(
        Enum("data_error", "system_failure", "complaint", "process_block", "performance", "other"),
        default="other",
        comment="问题类型",
    )
    status = Column(
        Enum("pending", "processing", "verify", "resolved", "closed", "suspended"),
        default="pending",
        comment="状态",
    )
    source = Column(String(64), default="manual", comment="来源")
    discovery_date = Column(DateTime, comment="发现时间")
    resolve_date = Column(DateTime, comment="解决时间")
    handler = Column(String(64), comment="处理人")
    impact_scope = Column(Text, comment="影响范围")
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
        Index("idx_issue_related_req", "related_req_id"),
        {"comment": "业务运营问题表"},
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
    host = Column(String(64), comment="主持人")
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

    __table_args__ = (
        Index("idx_meeting_start_time", "start_time"),
        Index("idx_meeting_related_req", "related_req_id"),
        {"comment": "会议表"},
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
