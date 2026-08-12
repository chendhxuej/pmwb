"""用户故事表：新增业务规则字段

Revision ID: 20260722000001
Revises: 20260720000001
Create Date: 2026-07-22 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260722000001"
down_revision: Union[str, None] = "20260720000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pmwb_user_story",
        sa.Column("rules", sa.Text(), nullable=True, comment="业务规则(JSON数组，每条一个规则描述)"),
    )


def downgrade() -> None:
    op.drop_column("pmwb_user_story", "rules")
