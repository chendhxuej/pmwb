"""add delivered_date to pmwb_requirement_ext

需求「实际交付/上线日期」字段：由用户在需求编辑界面手工选择填入，
用于 AI 总结中精确判定「本期上线需求」，替代原先 status=closed 时
用 updated_at 作代理的近似口径。
"""
from alembic import op
import sqlalchemy as sa


revision = "20260814000002"
down_revision = "20260814000001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "pmwb_requirement_ext",
        sa.Column(
            "delivered_date",
            sa.Date(),
            nullable=True,
            comment="实际交付/上线日期，由用户在需求编辑界面手工选择填入",
        ),
    )


def downgrade():
    op.drop_column("pmwb_requirement_ext", "delivered_date")
