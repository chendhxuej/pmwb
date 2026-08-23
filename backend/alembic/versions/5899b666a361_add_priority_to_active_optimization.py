"""add priority to active_optimization

Revision ID: 5899b666a361
Revises: 1a2df557c710
Create Date: 2026-08-23 22:43:35.744213

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '5899b666a361'
down_revision: Union[str, None] = '1a2df557c710'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'pmwb_active_optimization',
        sa.Column('priority', sa.String(length=16), nullable=True, server_default='P2', comment='优先级：P0/P1/P2/P3'),
    )


def downgrade() -> None:
    op.drop_column('pmwb_active_optimization', 'priority')
