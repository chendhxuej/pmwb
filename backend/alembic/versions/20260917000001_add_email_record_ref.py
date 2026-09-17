"""add ref_type/ref_id to email_records (邮件督办记录统一化)

将邮件发送记录稳定关联到具体工单/业务对象，替代仅 req_id 的松散关联。
P0 后端：模型加列 + 本迁移 + dispatch_email 透传 + 新增 GET /mail-dispatch/records。

Revision ID: 20260917000001
Revises: 20260914000002
"""
from alembic import op
import sqlalchemy as sa

revision = '20260917000001'
down_revision = '20260914000002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_records",
        sa.Column("ref_type", sa.String(64), comment="关联模块类型(operation/research/meeting_action/meeting/requirement/task_center/keywork/active_optimization/work_report/plugin)"),
    )
    op.add_column(
        "email_records",
        sa.Column("ref_id", sa.String(255), comment="关联业务主键/编号(issue_no/req_no/action_id 等)"),
    )
    op.create_index("idx_email_record_ref", "email_records", ["ref_type", "ref_id"])


def downgrade() -> None:
    op.drop_index("idx_email_record_ref", table_name="email_records")
    op.drop_column("email_records", "ref_id")
    op.drop_column("email_records", "ref_type")
