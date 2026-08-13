"""kc4-4: pmwb_requirement_ext 增加直挂交付物 deliverables

Revision ID: 20260812000003
Revises: 20260812000002
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision = '20260812000003'
down_revision = '20260812000002'
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'pmwb_requirement_ext',
        sa.Column(
            'deliverables',
            sa.Text(),
            nullable=True,
            comment='需求直挂交付物(JSON数组),每项含file_name/local_path/note/archived_at',
        ),
    )
    # MySQL TEXT 列不允许 server_default, 用 UPDATE 回填存量
    op.execute("UPDATE pmwb_requirement_ext SET deliverables = '[]' WHERE deliverables IS NULL")
    op.alter_column('pmwb_requirement_ext', 'deliverables', existing_type=sa.Text(), nullable=False)


def downgrade() -> None:
    op.drop_column('pmwb_requirement_ext', 'deliverables')
