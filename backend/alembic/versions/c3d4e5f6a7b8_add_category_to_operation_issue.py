"""Add category to pmwb_operation_issue (5 work-order categories)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-16 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'pmwb_operation_issue',
        sa.Column(
            'category',
            sa.Enum('bug', 'data', 'prod', 'task', 'complaint', name='wo_category'),
            nullable=False,
            server_default='prod',
            comment='工单大类：BUG管理/数据异常管理/生产问题分析/临时交办任务/热点投诉',
        ),
    )

    # 按原 issue_type 回填大类，保证历史数据归类正确
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE pmwb_operation_issue SET category = CASE issue_type
                WHEN 'data_error' THEN 'data'
                WHEN 'system_failure' THEN 'bug'
                WHEN 'performance' THEN 'bug'
                WHEN 'complaint' THEN 'complaint'
                WHEN 'process_block' THEN 'prod'
                ELSE 'prod' END
            """
        )
    )

    op.create_index('idx_issue_category', 'pmwb_operation_issue', ['category'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_issue_category', table_name='pmwb_operation_issue')
    op.drop_column('pmwb_operation_issue', 'category')
