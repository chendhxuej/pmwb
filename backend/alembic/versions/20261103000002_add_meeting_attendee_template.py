"""会议管理：参会人预制模板表（pmwb_meeting_attendee_template）

背景（2026-11-03 会议弹窗优化第三轮）：
  - 按会议类型挂载参会人预制模板，会议弹窗内一键批量填入（追加去重）；
  - meeting_type 关联 pmwb_meeting_type.name（中文名直落，无 code，改名由类型服务级联）；
  - members 存姓名 JSON 数组，与 pmwb_meeting_attendee.name 同口径。

  幂等性：建表先探测，存在则跳过，可安全重复执行。

Revision ID: 20261103000002
Revises: 20261103000001
Create Date: 2026-11-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20261103000002"
down_revision: Union[str, None] = "20261103000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TEMPLATE_TABLE = "pmwb_meeting_attendee_template"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TEMPLATE_TABLE in inspector.get_table_names():
        return

    op.create_table(
        TEMPLATE_TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("meeting_type", sa.String(length=64), nullable=False, comment="关联会议类型名"),
        sa.Column("name", sa.String(length=64), nullable=False, comment="模板名称"),
        sa.Column("members", sa.Text(), nullable=True, comment="成员姓名 JSON 数组"),
        sa.Column("sort_order", sa.Integer(), nullable=True, server_default="0", comment="排序号"),
        sa.Column("enabled", sa.Boolean(), nullable=True, server_default="1", comment="是否启用"),
        sa.Column("remark", sa.String(length=255), nullable=True, comment="用途说明"),
        sa.Column("created_at", sa.DateTime(), nullable=True, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=True, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        comment="会议参会人预制模板",
    )
    op.create_index(
        "ix_pmwb_meeting_attendee_template_meeting_type",
        TEMPLATE_TABLE,
        ["meeting_type"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TEMPLATE_TABLE in inspector.get_table_names():
        op.drop_index(
            "ix_pmwb_meeting_attendee_template_meeting_type",
            table_name=TEMPLATE_TABLE,
        )
        op.drop_table(TEMPLATE_TABLE)
