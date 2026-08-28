"""add pmwb_key_work_weekly_feedback

Revision ID: 20260828000001
Revises: 20260827000001
Create Date: 2026-08-28 11:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260828000001'
down_revision: Union[str, None] = '20260827000001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pmwb_key_work_weekly_feedback',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('key_work_id', sa.Integer(), nullable=False, comment='关联重点工作ID'),
        sa.Column('week', sa.String(length=10), nullable=False, comment='周次 YYYY-Www'),
        sa.Column('assignee', sa.String(length=64), nullable=False, comment='责任人'),
        sa.Column('source', sa.String(length=16), nullable=False, server_default='manual', comment='来源: manual/email/link'),
        sa.Column('feedback_date', sa.Date(), nullable=True, comment='反馈日期'),
        sa.Column('done_summary', sa.Text(), nullable=True, comment='本周完成'),
        sa.Column('next_summary', sa.Text(), nullable=True, comment='下周计划'),
        sa.Column('risk_note', sa.Text(), nullable=True, comment='风险/求助'),
        sa.Column('progress', sa.Integer(), nullable=True, comment='该责任人进度% 0-100'),
        sa.Column('item_updates', sa.Text(), nullable=True, comment='子项状态更新明细 JSON'),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='submitted', comment='状态: submitted/confirmed'),
        sa.Column('raw_text', sa.Text(), nullable=True, comment='原始反馈全文（邮件原文等）'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['key_work_id'], ['pmwb_key_work.id'], ),
        sa.PrimaryKeyConstraint('id'),
        mysql_comment='重点工作周反馈表',
    )
    op.create_index('idx_kwwf_kw_week', 'pmwb_key_work_weekly_feedback', ['key_work_id', 'week'])
    op.create_index('idx_kwwf_assignee', 'pmwb_key_work_weekly_feedback', ['assignee'])


def downgrade() -> None:
    op.drop_index('idx_kwwf_assignee', table_name='pmwb_key_work_weekly_feedback')
    op.drop_index('idx_kwwf_kw_week', table_name='pmwb_key_work_weekly_feedback')
    op.drop_table('pmwb_key_work_weekly_feedback')
