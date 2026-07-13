"""Add is_overdue to todo table

Revision ID: 5f212592fbb2
Revises: 20260713000001
Create Date: 2026-07-13 20:31:35.177639

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f212592fbb2'
down_revision: Union[str, None] = '20260713000001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('pmwb_todo', sa.Column('is_overdue', sa.Integer(), nullable=True, comment='是否超期'))


def downgrade() -> None:
    op.drop_column('pmwb_todo', 'is_overdue')
