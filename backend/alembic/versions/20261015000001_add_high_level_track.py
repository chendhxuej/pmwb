"""新增 pmwb_high_level_track 表：任务中心「高级别工单」跟踪态

背景（任务中心「高级别工单」子模块，2026-10-15）：
  任务中心原为**纯实时聚合、零落库**的只读视图（services/task_center.py）。
  新增子模块需要「汇聚跟踪」能力（首次发现/最近命中/跟踪态/督办次数/人工锁定），
  故新增一张**轻量表**，只承载跟踪态，**不复制工单本体**：
    - 工单标题/负责人/截止/状态等仍实时回读各来源表；
    - 唯一锚点 (source, source_id)，与任务中心 task_id（`source:source_id`）同构。

  幂等性：upgrade/downgrade 均先探测表是否存在，存在则跳过，可安全重复执行。
  注：应用启动时 `main.py` 也会 `Base.metadata.create_all`，本迁移供显式迁移链使用。

Revision ID: 20261015000001
Revises: 20261012000002
Create Date: 2026-10-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20261015000001"
down_revision: Union[str, None] = "20261012000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "pmwb_high_level_track"


def _has_table(bind) -> bool:
    return TABLE in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind):
        return  # 幂等跳过

    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("source", sa.String(length=32), nullable=False,
                  comment="任务来源（schemas/task_center.TASK_SOURCES）"),
        sa.Column("source_id", sa.String(length=64), nullable=False,
                  comment="源表主键/复合键（key_work 形如 task-12）"),
        sa.Column("is_high", sa.Integer(), nullable=False, server_default=sa.text("0"),
                  comment="当前是否高级别（规则+人工合成）"),
        sa.Column("judge_reason", sa.String(length=255), nullable=True,
                  comment="判定来源：R1:P0 / R2:overdue:P2:12d / R3:inherit:.. / R4:lock"),
        sa.Column("level_code", sa.String(length=8), nullable=True, comment="命中级别码 P0/P1/P2"),
        sa.Column("manual_override", sa.String(length=16), nullable=True,
                  comment="人工覆盖：lock 锁定 / escalate 提级 / dismiss 移出 / NULL 无"),
        sa.Column("track_status", sa.String(length=32), nullable=False, server_default=sa.text("'open'"),
                  comment="跟踪态（见 status_registry: high_level_track）"),
        sa.Column("urge_count", sa.Integer(), nullable=False, server_default=sa.text("0"),
                  comment="累计督办次数"),
        sa.Column("last_urged_at", sa.DateTime(), nullable=True, comment="最近一次督办时间"),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False, comment="首次纳入时间"),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False, comment="最近一次采集命中时间"),
        sa.Column("first_overdue_at", sa.Date(), nullable=True, comment="首次超期日期"),
        sa.Column("resolved_at", sa.DateTime(), nullable=True, comment="自动/人工闭环时间"),
        sa.Column("removed_at", sa.DateTime(), nullable=True, comment="源工单消失/人工移出时间"),
        sa.Column("operator", sa.String(length=64), nullable=True, comment="最近操作人（留痕）"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "source_id", name="uk_hl_source"),
        comment="高级别工单跟踪表（仅存跟踪态，不复制工单本体）",
    )
    op.create_index("idx_hl_pool", TABLE, ["is_high", "track_status"])
    op.create_index("idx_hl_status", TABLE, ["track_status"])
    op.create_index("idx_hl_seen", TABLE, ["last_seen_at"])
    op.create_index("idx_hl_override", TABLE, ["manual_override"])


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind):
        return  # 幂等跳过
    op.drop_table(TABLE)
