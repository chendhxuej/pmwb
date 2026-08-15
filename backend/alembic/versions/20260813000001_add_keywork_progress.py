"""add progress column to pmwb_key_work

重点工作主表补 progress 字段，支撑专题/年度/试点工作的进度管理与列表展示。
默认 0，存量数据全部为 0（此前无该列，前端恒显 0%）。
"""
from alembic import op
import sqlalchemy as sa


revision = "20260813000001"
down_revision = "20260812000003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "pmwb_key_work",
        sa.Column(
            "progress",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="进度百分比 0-100",
        ),
    )


def downgrade():
    op.drop_column("pmwb_key_work", "progress")
