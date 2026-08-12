"""业务表添加 staff_id 外键（人员中台化迁移）。

单值字段新增 nullable staff_id 列；多值字段使用 JSON 数组列。
原有字符串字段全部保留，双写过渡。

Revision ID: 20260727000001
"""
from alembic import op
import sqlalchemy as sa

revision: str = "20260727000001"
down_revision: str = "20260725000002"
branch_labels: tuple = None
depends_on: tuple = None


def upgrade() -> None:
    # ---- 单值字段 ----

    # pmwb_requirement_ext: sa_name → sa_staff_id
    op.add_column("pmwb_requirement_ext", sa.Column("sa_staff_id", sa.Integer(), nullable=True, comment="SA人员ID"))

    # pmwb_dev_ticket_log: operator → operator_staff_id
    op.add_column("pmwb_dev_ticket_log", sa.Column("operator_staff_id", sa.Integer(), nullable=True, comment="操作人ID"))

    # pmwb_meeting: host/convener/recorder → *_staff_id
    op.add_column("pmwb_meeting", sa.Column("host_staff_id", sa.Integer(), nullable=True, comment="主持人ID"))
    op.add_column("pmwb_meeting", sa.Column("convener_staff_id", sa.Integer(), nullable=True, comment="召集人ID"))
    op.add_column("pmwb_meeting", sa.Column("recorder_staff_id", sa.Integer(), nullable=True, comment="记录人ID"))

    # pmwb_meeting: absentees → absentee_staff_ids (JSON 数组)
    op.add_column("pmwb_meeting", sa.Column("absentee_staff_ids", sa.JSON(), nullable=True, comment="缺席人员ID列表[JSON数组]"))

    # pmwb_meeting_attendee: name → staff_id
    op.add_column("pmwb_meeting_attendee", sa.Column("staff_id", sa.Integer(), nullable=True, comment="参会人ID"))

    # pmwb_meeting_action: owner → owner_staff_id
    op.add_column("pmwb_meeting_action", sa.Column("owner_staff_id", sa.Integer(), nullable=True, comment="负责人ID"))

    # pmwb_requirement_evaluation: proposer/sa_name
    op.add_column("pmwb_requirement_evaluation", sa.Column("proposer_staff_id", sa.Integer(), nullable=True, comment="提出人ID"))
    op.add_column("pmwb_requirement_evaluation", sa.Column("sa_staff_id", sa.Integer(), nullable=True, comment="SA人员ID"))

    # sent_emails: proposer/sa_name (只读表，加列用于回填对齐)
    op.add_column("sent_emails", sa.Column("proposer_staff_id", sa.Integer(), nullable=True, comment="提出人ID"))
    op.add_column("sent_emails", sa.Column("sa_staff_id", sa.Integer(), nullable=True, comment="SA人员ID"))

    # email_records: recipient_name/sender
    op.add_column("email_records", sa.Column("recipient_staff_id", sa.Integer(), nullable=True, comment="收件人ID"))
    op.add_column("email_records", sa.Column("sender_staff_id", sa.Integer(), nullable=True, comment="发件人ID"))

    # sa_info: sa_name → staff_id (用于迁移对齐)
    op.add_column("sa_info", sa.Column("staff_id", sa.Integer(), nullable=True, comment="对齐人员中台ID"))

    # pmwb_key_work: owner → owner_staff_id
    op.add_column("pmwb_key_work", sa.Column("owner_staff_id", sa.Integer(), nullable=True, comment="负责人ID"))

    # pmwb_key_work_member: name → staff_id
    op.add_column("pmwb_key_work_member", sa.Column("staff_id", sa.Integer(), nullable=True, comment="成员ID"))

    # pmwb_key_work_progress: reporter → reporter_staff_id
    op.add_column("pmwb_key_work_progress", sa.Column("reporter_staff_id", sa.Integer(), nullable=True, comment="汇报人ID"))

    # pmwb_key_work_member_task: assignee → assignee_staff_id
    op.add_column("pmwb_key_work_member_task", sa.Column("assignee_staff_id", sa.Integer(), nullable=True, comment="指派人ID"))

    # ---- 多值字段（JSON 数组） ----

    # pmwb_operation_issue: handler(逗号分隔) → handler_staff_ids (JSON)
    op.add_column("pmwb_operation_issue", sa.Column("handler_staff_ids", sa.JSON(), nullable=True, comment="处理人ID列表[JSON数组]"))


def downgrade() -> None:
    # pmwb_requirement_ext
    op.drop_column("pmwb_requirement_ext", "sa_staff_id")

    # pmwb_dev_ticket_log
    op.drop_column("pmwb_dev_ticket_log", "operator_staff_id")

    # pmwb_meeting
    op.drop_column("pmwb_meeting", "absentee_staff_ids")
    op.drop_column("pmwb_meeting", "recorder_staff_id")
    op.drop_column("pmwb_meeting", "convener_staff_id")
    op.drop_column("pmwb_meeting", "host_staff_id")

    # pmwb_meeting_attendee
    op.drop_column("pmwb_meeting_attendee", "staff_id")

    # pmwb_meeting_action
    op.drop_column("pmwb_meeting_action", "owner_staff_id")

    # pmwb_requirement_evaluation
    op.drop_column("pmwb_requirement_evaluation", "sa_staff_id")
    op.drop_column("pmwb_requirement_evaluation", "proposer_staff_id")

    # sent_emails
    op.drop_column("sent_emails", "sa_staff_id")
    op.drop_column("sent_emails", "proposer_staff_id")

    # email_records
    op.drop_column("email_records", "sender_staff_id")
    op.drop_column("email_records", "recipient_staff_id")

    # sa_info
    op.drop_column("sa_info", "staff_id")

    # pmwb_key_work
    op.drop_column("pmwb_key_work", "owner_staff_id")

    # pmwb_key_work_member
    op.drop_column("pmwb_key_work_member", "staff_id")

    # pmwb_key_work_progress
    op.drop_column("pmwb_key_work_progress", "reporter_staff_id")

    # pmwb_key_work_member_task
    op.drop_column("pmwb_key_work_member_task", "assignee_staff_id")

    # pmwb_operation_issue
    op.drop_column("pmwb_operation_issue", "handler_staff_ids")
