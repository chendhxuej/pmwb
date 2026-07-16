"""Add version_required_date to pmwb_requirement_ext

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-16 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'pmwb_requirement_ext',
        sa.Column(
            'version_required_date',
            sa.Date(),
            nullable=True,
            comment='版本要求(需求管理要求的上线时间)',
        ),
    )


def downgrade() -> None:
    op.drop_column('pmwb_requirement_ext', 'version_required_date')
