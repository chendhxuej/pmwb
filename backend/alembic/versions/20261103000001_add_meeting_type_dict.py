"""会议管理：会议类型字典表（pmwb_meeting_type）

背景（会议模块优化三项之一，2026-11-03 老大拍板）：
  - pmwb_meeting_type：类型字典表（name 唯一，支持启停/排序/展示色），
    唯一真相源——pmwb_meeting.meeting_type 直接落本表 name 中文名，
    沿需求分类字典（pmwb_requirement_category）先例，禁在别处另存枚举；
  - 存量会议 meeting_type 为英文 code（旧 MeetingType 枚举），本迁移幂等回填为中文名；
  - pmwb_meeting.meeting_type 列宽 32 → 64（对齐字典表 name 宽度）。

  幂等性：建表/回填均先探测，存在则跳过，可安全重复执行。

Revision ID: 20261103000001
Revises: 20261030000002
Create Date: 2026-11-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20261103000001"
down_revision: Union[str, None] = "20261030000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TYPE_TABLE = "pmwb_meeting_type"

# 存量 code → 中文名映射（沿旧前端 meetingTypeOptions 口径），color 沿旧 typeTagMap
PRESET_TYPES = [
    ("需求讨论", 10, "amber"),
    ("问题分析", 20, "red"),
    ("内部例会", 30, "blue"),
    ("外部对接", 40, "green"),
    ("党会", 50, "red"),
    ("集团会议", 60, "blue"),
    ("其他", 90, "gray"),
]
CODE_TO_NAME = {
    "requirement_discussion": "需求讨论",
    "problem_analysis": "问题分析",
    "internal_regular": "内部例会",
    "external_sync": "外部对接",
    "party_meeting": "党会",
    "group_meeting": "集团会议",
    "other": "其他",
}


def _has_table(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def _has_column(bind, table: str, column: str) -> bool:
    return column in [c["name"] for c in inspect(bind).get_columns(table)]


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, TYPE_TABLE):
        op.create_table(
            TYPE_TABLE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
            sa.Column("name", sa.String(64), nullable=False, comment="类型名称，即会议落库值"),
            sa.Column("sort_order", sa.Integer(), nullable=True, comment="排序号，越小越靠前"),
            sa.Column(
                "enabled", sa.Boolean(), nullable=True,
                comment="是否启用，停用后不出现在下拉但存量会议保留展示",
            ),
            sa.Column(
                "color", sa.String(16), nullable=True,
                comment="展示色（语义名：amber/red/blue/green/purple/gray）",
            ),
            sa.Column("remark", sa.String(255), nullable=True, comment="用途说明，便于后续维护"),
            sa.Column("created_at", sa.DateTime(), nullable=True, comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), nullable=True, comment="更新时间"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
            {"comment": "会议类型字典"},
        )

    # 种子：INSERT ... WHERE NOT EXISTS 幂等，防迁移重放重复插入
    for name, sort_order, color in PRESET_TYPES:
        bind.execute(
            sa.text(
                f"INSERT INTO {TYPE_TABLE} (name, sort_order, enabled, color, created_at, updated_at) "
                "SELECT :name, :sort_order, 1, :color, NOW(), NOW() "
                "FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM " + TYPE_TABLE + " WHERE name = :name)"
            ),
            {"name": name, "sort_order": sort_order, "color": color},
        )

    # 存量会议类型回填：仅仍为旧英文 code 的行（幂等，中文名行不受影响）
    for code, name in CODE_TO_NAME.items():
        bind.execute(
            sa.text(
                "UPDATE pmwb_meeting SET meeting_type = :name "
                "WHERE meeting_type = :code"
            ),
            {"name": name, "code": code},
        )

    # 列宽 32 → 64（对齐字典表 name；幂等：已 64 时 MODIFY 无副作用）
    if _has_column(bind, "pmwb_meeting", "meeting_type"):
        bind.execute(
            sa.text(
                "ALTER TABLE pmwb_meeting MODIFY COLUMN meeting_type VARCHAR(64) "
                "NULL DEFAULT '其他' COMMENT '会议类型（pmwb_meeting_type.name，唯一真相源）'"
            )
        )


def downgrade() -> None:
    # 字典表为增量能力，不回滚存量数据回填（回滚会把已中文化的类型名留在会议表，仍可读）
    bind = op.get_bind()
    if _has_table(bind, TYPE_TABLE):
        op.drop_table(TYPE_TABLE)
