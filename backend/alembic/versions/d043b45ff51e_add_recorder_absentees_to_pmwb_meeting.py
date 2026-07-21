"""add recorder absentees to pmwb_meeting

Revision ID: d043b45ff51e
Revises: 20260721000002
Create Date: 2026-07-21 16:32:43.155445

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd043b45ff51e'
down_revision: Union[str, None] = '20260721000002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('pmwb_meeting', sa.Column('recorder', sa.String(length=64), nullable=True, comment='记录人'))
    op.add_column('pmwb_meeting', sa.Column('absentees', sa.Text(), nullable=True, comment='缺席人/请假说明'))


def downgrade() -> None:
    op.drop_column('pmwb_meeting', 'absentees')
    op.drop_column('pmwb_meeting', 'recorder')
