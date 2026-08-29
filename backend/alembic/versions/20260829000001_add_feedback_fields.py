"""add monthly_summary/next_month_summary/member_task_notes/deliverable_ids to weekly feedback

Revision ID: 20260829000001
Revises: 20260828000001
Create Date: 2026-08-29 11:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260829000001'
down_revision: Union[str, None] = '20260828000001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'pmwb_key_work_weekly_feedback',
        sa.Column('monthly_summary', sa.Text(), nullable=True, comment='本月月总结（月底周）')
    )
    op.add_column(
        'pmwb_key_work_weekly_feedback',
        sa.Column('next_month_summary', sa.Text(), nullable=True, comment='下月重点/下月月计划草案（月底周）')
    )
    op.add_column(
        'pmwb_key_work_weekly_feedback',
        sa.Column('member_task_notes', sa.Text(), nullable=True, comment='成员任务进展说明 JSON [{task_id, note, status}]')
    )
    op.add_column(
        'pmwb_key_work_weekly_feedback',
        sa.Column('deliverable_ids', sa.Text(), nullable=True, comment='本次反馈关联交付物ID列表 JSON')
    )


def downgrade() -> None:
    op.drop_column('pmwb_key_work_weekly_feedback', 'deliverable_ids')
    op.drop_column('pmwb_key_work_weekly_feedback', 'member_task_notes')
    op.drop_column('pmwb_key_work_weekly_feedback', 'next_month_summary')
    op.drop_column('pmwb_key_work_weekly_feedback', 'monthly_summary')
