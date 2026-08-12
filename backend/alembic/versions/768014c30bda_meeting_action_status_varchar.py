"""meeting_action_status_varchar

会议行动项状态扩展为：待办(pending)、进行中(in_progress)、已完成(done)、没参会(not_attended)。

Revision ID: 768014c30bda
Revises: 11b02ea8bf67
Create Date: 2026-07-22 12:35:10.321951

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "768014c30bda"
down_revision: Union[str, None] = "11b02ea8bf67"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "pmwb_meeting_action",
        "status",
        existing_type=mysql.ENUM(
            "pending",
            "done",
            "cancelled",
            collation="utf8mb4_unicode_ci",
        ),
        type_=sa.String(length=32),
        existing_comment="状态",
        existing_nullable=True,
        existing_server_default=sa.text("'pending'"),
    )


def downgrade() -> None:
    op.alter_column(
        "pmwb_meeting_action",
        "status",
        existing_type=sa.String(length=32),
        type_=mysql.ENUM(
            "pending",
            "done",
            "cancelled",
            collation="utf8mb4_unicode_ci",
        ),
        existing_comment="状态",
        existing_nullable=True,
        existing_server_default=sa.text("'pending'"),
    )
