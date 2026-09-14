"""keywork weekly plan: week 改为可空（界面不再录入周次）

Revision ID: 20260914000001
Revises: a7c3e91d4b28
Create Date: 2026-09-14 15:05:00

周计划定位调整：只记录「本周要达成的任务目标」，责任人下沉到成员待办（可选关联）。
界面删掉「周次」「责任人」录入后，周次由后端按创建日期自动推算，
因此 week 列需允许为空（历史数据保留不动）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260914000001'
down_revision: Union[str, Sequence[str], None] = 'a7c3e91d4b28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'pmwb_key_work_weekly_plan',
        'week',
        existing_type=sa.String(length=10),
        nullable=True,
        comment='周次 YYYY-Www（界面不再录入，由系统按创建日期自动推算）',
    )


def downgrade() -> None:
    op.alter_column(
        'pmwb_key_work_weekly_plan',
        'week',
        existing_type=sa.String(length=10),
        nullable=False,
        comment='周次 YYYY-Www',
    )
