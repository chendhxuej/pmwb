"""meeting_status_not_attended

Revision ID: 89c1d2bf42c5
Revises: 6eb2861442a5
Create Date: 2026-07-22 16:11:07.626893

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '89c1d2bf42c5'
down_revision: Union[str, None] = '6eb2861442a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'pmwb_meeting',
        'status',
        existing_type=mysql.ENUM('planned', 'held', 'cancelled', collation='utf8mb4_unicode_ci'),
        type_=sa.Enum('planned', 'held', 'cancelled', 'not_attended'),
        existing_comment='状态',
        existing_nullable=True,
        existing_server_default=sa.text("'planned'"),
    )


def downgrade() -> None:
    op.alter_column(
        'pmwb_meeting',
        'status',
        existing_type=sa.Enum('planned', 'held', 'cancelled', 'not_attended'),
        type_=mysql.ENUM('planned', 'held', 'cancelled', collation='utf8mb4_unicode_ci'),
        existing_comment='状态',
        existing_nullable=True,
        existing_server_default=sa.text("'planned'"),
    )
