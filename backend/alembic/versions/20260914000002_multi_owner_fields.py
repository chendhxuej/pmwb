"""成员待办负责人 / 会议行动项负责人：扩容为多值（逗号分隔）

Revision ID: 20260914000002
Revises: 20260914000001
Create Date: 2026-09-14 15:35:00

- pmwb_key_work_member_task.assignee: VARCHAR(64) -> VARCHAR(512)
- pmwb_meeting_action.owner:          VARCHAR(64) -> VARCHAR(512)

存储约定沿用运营监控工单 handler 的既有做法：前端多选数组 join(',') 落库、
展示时 split(',') 成标签，不做多对多关联表，避免动周报/邮件/督办全链路。
历史单值数据天然兼容（无逗号即为单责任人），无需数据迁移。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260914000002'
down_revision: Union[str, Sequence[str], None] = '20260914000001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'pmwb_key_work_member_task',
        'assignee',
        existing_type=sa.String(length=64),
        type_=sa.String(length=512),
        existing_comment='负责人(成员姓名)',
        comment='负责人(成员姓名,多选,逗号分隔)',
    )
    op.alter_column(
        'pmwb_meeting_action',
        'owner',
        existing_type=sa.String(length=64),
        type_=sa.String(length=512),
        existing_comment='负责人',
        comment='负责人(多选,逗号分隔)',
    )


def downgrade() -> None:
    op.alter_column(
        'pmwb_meeting_action',
        'owner',
        existing_type=sa.String(length=512),
        type_=sa.String(length=64),
        existing_comment='负责人(多选,逗号分隔)',
        comment='负责人',
    )
    op.alter_column(
        'pmwb_key_work_member_task',
        'assignee',
        existing_type=sa.String(length=512),
        type_=sa.String(length=64),
        existing_comment='负责人(成员姓名,多选,逗号分隔)',
        comment='负责人(成员姓名)',
    )
