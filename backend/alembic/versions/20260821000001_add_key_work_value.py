"""重点工作主表增加工作价值字段

为 pmwb_key_work 增加：
- work_value: Text，记录工作价值/收益
"""
from alembic import op
import sqlalchemy as sa


revision = "20260821000001"
down_revision = "20260817000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pmwb_key_work",
        sa.Column("work_value", sa.Text(), nullable=True, comment="工作价值/收益"),
    )


def downgrade() -> None:
    op.drop_column("pmwb_key_work", "work_value")
