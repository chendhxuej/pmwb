"""Add pmwb_requirement_evaluation table

Revision ID: a1b2c3d4e5f6
Revises: 5f212592fbb2
Create Date: 2026-07-14 13:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '5f212592fbb2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pmwb_requirement_evaluation',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='自增ID'),
        sa.Column('sent_email_id', sa.Integer(), nullable=False, comment='关联 sent_emails.id（每个团队评估记录一条）'),
        sa.Column('req_id', sa.String(length=255), nullable=True, comment='需求编号，冗余便于查询'),
        sa.Column('workload', sa.Numeric(precision=10, scale=2), nullable=True, comment='工作量评估(人天)'),
        sa.Column('opinion', sa.Text(), nullable=True, comment='评估意见登记'),
        sa.Column('dev_ticket_no', sa.String(length=255), nullable=True, comment='开发单号'),
        sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sent_email_id', name='uk_eval_sent_email'),
        comment='需求团队评估扩展表',
    )
    op.create_index('idx_eval_req_id', 'pmwb_requirement_evaluation', ['req_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_eval_req_id', table_name='pmwb_requirement_evaluation')
    op.drop_table('pmwb_requirement_evaluation')
