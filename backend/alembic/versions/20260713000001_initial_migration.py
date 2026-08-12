"""Initial migration for pmwb tables

Revision ID: 20260713000001
Revises: 
Create Date: 2026-07-13 14:21:02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260713000001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pmwb_requirement_ext
    op.create_table(
        "pmwb_requirement_ext",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("req_id", sa.String(64), nullable=False, comment="需求编号，对应 sent_emails.req_id"),
        sa.Column("status", sa.String(64), server_default="proposed", comment="个人跟踪状态"),
        sa.Column("tags", sa.String(512), nullable=True, comment="个人标签，逗号分隔"),
        sa.Column("personal_note", sa.Text(), nullable=True, comment="个人备注"),
        sa.Column("priority", sa.Enum("P0", "P1", "P2", "P3"), server_default="P2", comment="个人优先级"),
        sa.Column("owner_note", sa.Text(), nullable=True, comment="负责人备忘"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("req_id"),
        comment="需求管理扩展表",
    )
    op.create_index("idx_req_status", "pmwb_requirement_ext", ["status"])

    # pmwb_dev_ticket
    op.create_table(
        "pmwb_dev_ticket",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("ticket_no", sa.String(64), nullable=False, comment="开发工单编号"),
        sa.Column("req_id", sa.String(64), nullable=False, comment="关联需求编号"),
        sa.Column("system_name", sa.String(128), nullable=False, comment="涉及系统"),
        sa.Column("dev_team", sa.String(64), nullable=True, comment="开发团队/厂商"),
        sa.Column("developer", sa.String(64), nullable=True, comment="开发负责人"),
        sa.Column("dev_contact", sa.String(128), nullable=True, comment="开发联系方式"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="工单创建时间"),
        sa.Column("design_reviewed_date", sa.Date(), nullable=True, comment="设计方案评审日期"),
        sa.Column("dev_completed_date", sa.Date(), nullable=True, comment="实际完成开发日期"),
        sa.Column("test_completed_date", sa.Date(), nullable=True, comment="测试完成日期"),
        sa.Column("go_live_date", sa.Date(), nullable=True, comment="实际上线日期"),
        sa.Column("archived_date", sa.Date(), nullable=True, comment="归档日期"),
        sa.Column(
            "status",
            sa.Enum("created", "design_reviewed", "dev_completed", "test_completed", "live", "archived"),
            server_default="created",
            comment="当前状态",
        ),
        sa.Column("progress", sa.Integer(), server_default="0", comment="进度百分比 0-100"),
        sa.Column("description", sa.Text(), nullable=True, comment="工单描述/开发内容"),
        sa.Column("risk_note", sa.Text(), nullable=True, comment="风险/延期原因"),
        sa.Column("deliverable_path", sa.String(512), nullable=True, comment="Obsidian交付物归档路径"),
        sa.Column("is_overdue", sa.Integer(), server_default="0", comment="是否超期"),
        sa.Column("priority", sa.Enum("P0", "P1", "P2", "P3"), server_default="P2", comment="优先级"),
        sa.Column("created_by", sa.String(64), nullable=True, comment="创建人"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_no", "system_name", name="uk_ticket_system"),
        comment="开发工单表",
    )
    op.create_index("idx_dev_req_id", "pmwb_dev_ticket", ["req_id"])
    op.create_index("idx_dev_status", "pmwb_dev_ticket", ["status"])

    # pmwb_dev_deliverable
    op.create_table(
        "pmwb_dev_deliverable",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("ticket_id", sa.Integer(), nullable=False, comment="关联 pmwb_dev_ticket.id"),
        sa.Column(
            "deliverable_type",
            sa.Enum("operation_manual", "interface_doc", "test_case", "release_note", "other"),
            server_default="other",
            comment="交付物类型",
        ),
        sa.Column("file_name", sa.String(255), nullable=False, comment="文件名"),
        sa.Column("original_name", sa.String(255), nullable=True, comment="原始文件名"),
        sa.Column("file_size", sa.Integer(), nullable=True, comment="文件大小(字节)"),
        sa.Column("file_type", sa.String(64), nullable=True, comment="文件MIME类型"),
        sa.Column("obsidian_path", sa.String(512), nullable=True, comment="Obsidian归档完整路径"),
        sa.Column("local_path", sa.String(512), nullable=True, comment="本地备份路径"),
        sa.Column("source", sa.String(32), server_default="upload", comment="来源"),
        sa.Column("source_url", sa.String(1024), nullable=True, comment="来源URL"),
        sa.Column("note", sa.Text(), nullable=True, comment="备注"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.ForeignKeyConstraint(["ticket_id"], ["pmwb_dev_ticket.id"]),
        sa.PrimaryKeyConstraint("id"),
        comment="开发交付物表",
    )
    op.create_index("idx_deliverable_ticket_id", "pmwb_dev_deliverable", ["ticket_id"])

    # pmwb_dev_ticket_log
    op.create_table(
        "pmwb_dev_ticket_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("ticket_id", sa.Integer(), nullable=False, comment="关联 pmwb_dev_ticket.id"),
        sa.Column("from_status", sa.String(32), nullable=True, comment="变更前状态"),
        sa.Column("to_status", sa.String(32), nullable=True, comment="变更后状态"),
        sa.Column("operator", sa.String(64), nullable=True, comment="操作人"),
        sa.Column("note", sa.Text(), nullable=True, comment="变更原因/备注"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.ForeignKeyConstraint(["ticket_id"], ["pmwb_dev_ticket.id"]),
        sa.PrimaryKeyConstraint("id"),
        comment="开发工单状态变更日志",
    )
    op.create_index("idx_log_ticket_id", "pmwb_dev_ticket_log", ["ticket_id"])

    # pmwb_todo
    op.create_table(
        "pmwb_todo",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("title", sa.String(255), nullable=False, comment="待办标题"),
        sa.Column("content", sa.Text(), nullable=True, comment="待办内容"),
        sa.Column("category", sa.String(64), server_default="other", comment="分类"),
        sa.Column("priority", sa.Enum("P0", "P1", "P2", "P3"), server_default="P2", comment="优先级"),
        sa.Column("status", sa.Enum("todo", "in_progress", "done", "cancelled"), server_default="todo", comment="状态"),
        sa.Column("due_date", sa.Date(), nullable=True, comment="截止日期"),
        sa.Column("due_time", sa.String(8), nullable=True, comment="截止时间"),
        sa.Column("remind_at", sa.DateTime(), nullable=True, comment="提醒时间"),
        sa.Column("repeat_type", sa.Enum("none", "daily", "weekly", "monthly"), server_default="none", comment="重复类型"),
        sa.Column("related_type", sa.String(64), nullable=True, comment="关联对象类型"),
        sa.Column("related_id", sa.String(64), nullable=True, comment="关联对象ID"),
        sa.Column("source", sa.String(64), server_default="manual", comment="来源"),
        sa.Column("completed_at", sa.DateTime(), nullable=True, comment="完成时间"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        comment="待办任务表",
    )
    op.create_index("idx_todo_status", "pmwb_todo", ["status"])
    op.create_index("idx_todo_due_date", "pmwb_todo", ["due_date"])
    op.create_index("idx_todo_related", "pmwb_todo", ["related_type", "related_id"])

    # pmwb_operation_issue
    op.create_table(
        "pmwb_operation_issue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("issue_no", sa.String(64), nullable=False, comment="问题编号"),
        sa.Column("title", sa.String(255), nullable=False, comment="问题标题"),
        sa.Column(
            "issue_type",
            sa.Enum("data_error", "system_failure", "complaint", "process_block", "performance", "other"),
            server_default="other",
            comment="问题类型",
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "verify", "resolved", "closed", "suspended"),
            server_default="pending",
            comment="状态",
        ),
        sa.Column("source", sa.String(64), server_default="manual", comment="来源"),
        sa.Column("discovery_date", sa.DateTime(), nullable=True, comment="发现时间"),
        sa.Column("resolve_date", sa.DateTime(), nullable=True, comment="解决时间"),
        sa.Column("handler", sa.String(64), nullable=True, comment="处理人"),
        sa.Column("impact_scope", sa.Text(), nullable=True, comment="影响范围"),
        sa.Column("impact_level", sa.Enum("P0", "P1", "P2", "P3"), server_default="P2", comment="影响等级"),
        sa.Column("root_cause", sa.Text(), nullable=True, comment="根因分析"),
        sa.Column("solution", sa.Text(), nullable=True, comment="解决方案"),
        sa.Column("related_req_id", sa.String(64), nullable=True, comment="关联需求编号"),
        sa.Column("related_ticket_no", sa.String(64), nullable=True, comment="关联开发工单编号"),
        sa.Column("related_system", sa.String(128), nullable=True, comment="关联系统"),
        sa.Column("obsidian_path", sa.String(512), nullable=True, comment="沉淀知识条目路径"),
        sa.Column("is_overdue", sa.Integer(), server_default="0", comment="是否超期"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issue_no"),
        comment="业务运营问题表",
    )
    op.create_index("idx_issue_status", "pmwb_operation_issue", ["status"])
    op.create_index("idx_issue_type", "pmwb_operation_issue", ["issue_type"])
    op.create_index("idx_issue_related_req", "pmwb_operation_issue", ["related_req_id"])

    # pmwb_meeting
    op.create_table(
        "pmwb_meeting",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("meeting_id", sa.String(64), nullable=False, comment="会议编号"),
        sa.Column("title", sa.String(255), nullable=False, comment="会议主题"),
        sa.Column(
            "meeting_type",
            sa.Enum("requirement_review", "project_weekly", "troubleshooting", "training", "other"),
            server_default="other",
            comment="会议类型",
        ),
        sa.Column("start_time", sa.DateTime(), nullable=True, comment="开始时间"),
        sa.Column("end_time", sa.DateTime(), nullable=True, comment="结束时间"),
        sa.Column("location", sa.String(255), nullable=True, comment="会议地点/线上链接"),
        sa.Column("host", sa.String(64), nullable=True, comment="主持人"),
        sa.Column("summary", sa.Text(), nullable=True, comment="会议纪要摘要"),
        sa.Column("obsidian_path", sa.String(512), nullable=True, comment="Obsidian 纪要路径"),
        sa.Column("related_req_id", sa.String(64), nullable=True, comment="关联需求编号"),
        sa.Column("related_ticket_no", sa.String(64), nullable=True, comment="关联开发工单编号"),
        sa.Column("status", sa.Enum("planned", "held", "cancelled"), server_default="planned", comment="状态"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meeting_id"),
        comment="会议表",
    )
    op.create_index("idx_meeting_start_time", "pmwb_meeting", ["start_time"])
    op.create_index("idx_meeting_related_req", "pmwb_meeting", ["related_req_id"])

    # pmwb_meeting_attendee
    op.create_table(
        "pmwb_meeting_attendee",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("meeting_id", sa.Integer(), nullable=False, comment="关联 pmwb_meeting.id"),
        sa.Column("name", sa.String(64), nullable=False, comment="参会人姓名"),
        sa.Column("email", sa.String(128), nullable=True, comment="邮箱"),
        sa.Column("dept", sa.String(128), nullable=True, comment="部门"),
        sa.Column("is_required", sa.Integer(), server_default="1", comment="是否必须参加"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.ForeignKeyConstraint(["meeting_id"], ["pmwb_meeting.id"]),
        sa.PrimaryKeyConstraint("id"),
        comment="会议参会人表",
    )
    op.create_index("idx_attendee_meeting_id", "pmwb_meeting_attendee", ["meeting_id"])

    # pmwb_meeting_action
    op.create_table(
        "pmwb_meeting_action",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("meeting_id", sa.Integer(), nullable=False, comment="关联 pmwb_meeting.id"),
        sa.Column("content", sa.Text(), nullable=False, comment="行动项内容"),
        sa.Column("owner", sa.String(64), nullable=True, comment="负责人"),
        sa.Column("due_date", sa.Date(), nullable=True, comment="截止日期"),
        sa.Column("status", sa.Enum("pending", "done", "cancelled"), server_default="pending", comment="状态"),
        sa.Column("related_todo_id", sa.Integer(), nullable=True, comment="关联 pmwb_todo.id"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.ForeignKeyConstraint(["meeting_id"], ["pmwb_meeting.id"]),
        sa.PrimaryKeyConstraint("id"),
        comment="会议行动项表",
    )
    op.create_index("idx_action_meeting_id", "pmwb_meeting_action", ["meeting_id"])

    # pmwb_knowledge_item
    op.create_table(
        "pmwb_knowledge_item",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("item_id", sa.String(64), nullable=False, comment="知识条目编号"),
        sa.Column("title", sa.String(255), nullable=False, comment="标题"),
        sa.Column(
            "category",
            sa.String(64),
            nullable=False,
            comment="分类：product/operation/requirement/meeting/personal/study",
        ),
        sa.Column("sub_category", sa.String(128), nullable=True, comment="子分类"),
        sa.Column("tags", sa.String(512), nullable=True, comment="标签，逗号分隔"),
        sa.Column("obsidian_path", sa.String(512), nullable=False, comment="Obsidian 文件路径"),
        sa.Column("source_type", sa.String(64), nullable=True, comment="来源类型"),
        sa.Column("source_id", sa.String(64), nullable=True, comment="来源对象ID"),
        sa.Column("summary", sa.Text(), nullable=True, comment="摘要"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_id"),
        comment="知识库条目索引表",
    )
    op.create_index("idx_knowledge_category", "pmwb_knowledge_item", ["category"])
    op.create_index("idx_knowledge_source", "pmwb_knowledge_item", ["source_type", "source_id"])


def downgrade() -> None:
    op.drop_table("pmwb_knowledge_item")
    op.drop_table("pmwb_meeting_action")
    op.drop_table("pmwb_meeting_attendee")
    op.drop_table("pmwb_meeting")
    op.drop_table("pmwb_operation_issue")
    op.drop_table("pmwb_todo")
    op.drop_table("pmwb_dev_ticket_log")
    op.drop_table("pmwb_dev_deliverable")
    op.drop_table("pmwb_dev_ticket")
    op.drop_table("pmwb_requirement_ext")
