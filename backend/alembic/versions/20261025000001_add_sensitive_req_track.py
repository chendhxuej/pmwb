"""新增敏感需求跟踪两张表：pmwb_sensitive_req_track / pmwb_sensitive_req_milestone

背景（需求与交付「敏感需求跟踪」子模块，2026-10-25）：
  P0/P1 等敏感需求需要端到端倒排跟踪与以团队为对象的调度督办：
    - pmwb_sensitive_req_track：跟踪主表，req_id 唯一锚点，只存跟踪态，
      需求本体与上线要求时间（ext.version_required_date）实时回读，不复制；
    - pmwb_sensitive_req_milestone：倒排里程碑，(req_id, team, stage) 唯一，
      管控粒度=需求×团队×阶段（老大 2026-10-25 拍板），每团队 5 阶段独立排期与督办。

  幂等性：upgrade/downgrade 均先探测表是否存在，存在则跳过，可安全重复执行。
  注：应用启动时 main.py 也会 Base.metadata.create_all，本迁移供显式迁移链使用。

Revision ID: 20261025000001
Revises: 20261017000001
Create Date: 2026-10-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20261025000001"
down_revision: Union[str, None] = "20261017000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TRACK = "pmwb_sensitive_req_track"
MILESTONE = "pmwb_sensitive_req_milestone"


def _has_table(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, TRACK):
        op.create_table(
            TRACK,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
            sa.Column("req_id", sa.String(length=64), nullable=False,
                      comment="需求编号，对应 pmwb_requirement_ext.req_id"),
            sa.Column("is_sensitive", sa.Integer(), nullable=False, server_default=sa.text("1"),
                      comment="当前是否敏感（规则+人工合成）"),
            sa.Column("judge_reason", sa.String(length=255), nullable=True,
                      comment="判定来源：R1:P0 / R1:集团需求 / R4:lock / R4:dismiss"),
            sa.Column("level_code", sa.String(length=8), nullable=True,
                      comment="命中级别码 P0/P1（自由文本时为空）"),
            sa.Column("manual_override", sa.String(length=16), nullable=True,
                      comment="人工覆盖：lock 锁定 / dismiss 移出 / NULL 无"),
            sa.Column("track_status", sa.String(length=32), nullable=False,
                      server_default=sa.text("'active'"),
                      comment="跟踪态（见 status_registry: sensitive_req_track）"),
            sa.Column("urge_count", sa.Integer(), nullable=False, server_default=sa.text("0"),
                      comment="累计督办次数"),
            sa.Column("last_urged_at", sa.DateTime(), nullable=True, comment="最近一次督办时间"),
            sa.Column("first_seen_at", sa.DateTime(), nullable=False, comment="首次纳入时间"),
            sa.Column("last_seen_at", sa.DateTime(), nullable=False, comment="最近一次采集命中时间"),
            sa.Column("first_overdue_at", sa.Date(), nullable=True,
                      comment="首次超期日期（首个里程碑超期日）"),
            sa.Column("resolved_at", sa.DateTime(), nullable=True, comment="自动/人工闭环时间"),
            sa.Column("removed_at", sa.DateTime(), nullable=True,
                      comment="源需求消失/人工移出时间"),
            sa.Column("operator", sa.String(length=64), nullable=True, comment="最近操作人（留痕）"),
            sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), nullable=False, comment="更新时间"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("req_id", name="uk_sr_req"),
            comment="敏感需求跟踪表（仅存跟踪态，不复制需求本体）",
        )
        op.create_index("idx_sr_pool", TRACK, ["is_sensitive", "track_status"])
        op.create_index("idx_sr_status", TRACK, ["track_status"])
        op.create_index("idx_sr_seen", TRACK, ["last_seen_at"])

    if not _has_table(bind, MILESTONE):
        op.create_table(
            MILESTONE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
            sa.Column("req_id", sa.String(length=64), nullable=False, comment="需求编号"),
            sa.Column("team_system_name", sa.String(length=128), nullable=False,
                      comment="团队标识=团队评估系统名（唯一链路 vendor_dev.active_team_systems）"),
            sa.Column("stage", sa.String(length=32), nullable=False,
                      comment="管控阶段: evaluate/plan/dev/test/deploy（敏感域专用枚举）"),
            sa.Column("owner", sa.String(length=255), nullable=True,
                      comment="阶段责任人（可多人，逗号分隔）"),
            sa.Column("planned_start", sa.Date(), nullable=True, comment="计划开始日期（倒排产物）"),
            sa.Column("planned_end", sa.Date(), nullable=True, comment="计划完成日期（倒排产物）"),
            sa.Column("actual_end", sa.Date(), nullable=True,
                      comment="实际完成日期（人工确认；dev/deploy 可参照 stage_log 提示）"),
            sa.Column("status", sa.String(length=32), server_default=sa.text("'pending'"),
                      comment="里程碑状态: pending/doing/done（见 status_registry: sensitive_milestone）"),
            sa.Column("risk_note", sa.String(length=500), nullable=True, comment="风险/备注"),
            sa.Column("source", sa.String(length=16), server_default=sa.text("'manual'"),
                      comment="来源: auto=倒排建议生成 / manual=人工"),
            sa.Column("urge_count", sa.Integer(), nullable=False, server_default=sa.text("0"),
                      comment="累计督办次数"),
            sa.Column("last_urged_at", sa.DateTime(), nullable=True, comment="最近一次督办时间"),
            sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), nullable=False, comment="更新时间"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("req_id", "team_system_name", "stage", name="uk_sr_milestone"),
            comment="敏感需求倒排里程碑（需求×团队×阶段）",
        )
        op.create_index("idx_sr_ms_req_id", MILESTONE, ["req_id"])
        op.create_index("idx_sr_ms_end", MILESTONE, ["planned_end"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, MILESTONE):
        op.drop_table(MILESTONE)
    if _has_table(bind, TRACK):
        op.drop_table(TRACK)
