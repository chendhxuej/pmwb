"""新增 pmwb_vendor_team / pmwb_req_vendor_dev 两表：需求「厂家开发状态」

背景（插件采集厂家开发单 + 需求状态联动，2026-10-16）：
  需求「生产部署」环节需要一个**按厂家**的开发状态维度，用于：
    1. 插件从待办页识别厂家开发单验收通知工单后，把对应厂家的开发状态置「已上线」；
    2. 人工逐家确认「已完成」，最后一家完成时触发需求级上线联动
       （跟踪状态 → 已上线，实际上线日 → 当周周四）。

  两表职责（务必区分，别搞混）：
    - pmwb_vendor_team：**别名映射字典**，只负责把工单标题里的厂家名/系统别名
      归一到 system_name。**不是**厂家清单的源头。
    - pmwb_req_vendor_dev：需求×厂家 的开发状态落地表。
      **厂家清单的源头是「团队评估」中 workload > 0 的系统**（读
      pmwb_requirement_evaluation），见 services/vendor_dev.py::active_team_systems。
      本表刻意**不存 workload**，避免与评估表两处口径打架。

  dev_status 为 String(32)（非 ENUM），合法值见 constants/status_registry.py
  的 vendor_dev 域：pending/developing/live/completed。

  幂等性：upgrade/downgrade 均先探测表是否存在，存在则跳过，可安全重复执行。
  注：应用启动时 main.py 也会 Base.metadata.create_all，本迁移供显式迁移链使用。

Revision ID: 20261016000001
Revises: 20261012000002
Create Date: 2026-10-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20261016000001"
down_revision: Union[str, None] = "20261012000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_TEAM = "pmwb_vendor_team"
TABLE_DEV = "pmwb_req_vendor_dev"


def _has_table(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, TABLE_TEAM):
        op.create_table(
            TABLE_TEAM,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
            sa.Column("team_name", sa.String(length=128), nullable=False,
                      comment="厂家团队名，如「卓望」"),
            sa.Column("system_name", sa.String(length=128), nullable=False,
                      comment="对应团队评估中的系统名（关联键），如「CRM」"),
            sa.Column("aliases", sa.String(length=512), nullable=True,
                      comment="工单标题中可能出现的别名，逗号分隔"),
            sa.Column("sort", sa.Integer(), nullable=True, server_default=sa.text("0"),
                      comment="排序"),
            sa.Column("enabled", sa.Integer(), nullable=True, server_default=sa.text("1"),
                      comment="是否启用 1/0"),
            sa.Column("created_at", sa.DateTime(), nullable=True, comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), nullable=True, comment="更新时间"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("team_name", name="uq_vendor_team_name"),
            comment="厂家团队别名映射字典",
        )
        op.create_index("idx_vendor_team_system", TABLE_TEAM, ["system_name"])

    if not _has_table(bind, TABLE_DEV):
        op.create_table(
            TABLE_DEV,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
            sa.Column("req_id", sa.String(length=64), nullable=False,
                      comment="需求编号，对应 sent_emails.req_id"),
            sa.Column("system_name", sa.String(length=128), nullable=False,
                      comment="厂家标识=团队评估系统名"),
            sa.Column("team_name", sa.String(length=128), nullable=True,
                      comment="厂家团队名（展示用，冗余自字典）"),
            sa.Column("sa_name", sa.String(length=64), nullable=True,
                      comment="该厂家负责人（展示用，冗余自团队评估）"),
            sa.Column("dev_ticket_no", sa.String(length=255), nullable=True,
                      comment="该厂家对应的开发单号"),
            sa.Column("dev_status", sa.String(length=32), nullable=True,
                      server_default=sa.text("'developing'"),
                      comment="开发状态 pending/developing/live/completed（见 status_registry，禁 ENUM）"),
            sa.Column("manual_file_name", sa.String(length=500), nullable=True,
                      comment="厂家操作手册原始文件名"),
            sa.Column("manual_local_path", sa.String(length=1024), nullable=True,
                      comment="厂家操作手册相对 vault 路径"),
            sa.Column("manual_archived_path", sa.String(length=512), nullable=True,
                      comment="厂家操作手册归档后的 Obsidian 路径"),
            sa.Column("manual_uploaded_at", sa.DateTime(), nullable=True,
                      comment="厂家操作手册上传时间"),
            sa.Column("source", sa.String(length=16), nullable=True,
                      server_default=sa.text("'manual'"), comment="来源：plugin/manual"),
            sa.Column("created_at", sa.DateTime(), nullable=True, comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), nullable=True, comment="更新时间"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("req_id", "system_name", name="uk_req_vendor_dev_system"),
            comment="需求×厂家开发状态（生产部署）",
        )
        op.create_index("idx_req_vendor_dev_req_id", TABLE_DEV, ["req_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, TABLE_DEV):
        op.drop_table(TABLE_DEV)
    if _has_table(bind, TABLE_TEAM):
        op.drop_table(TABLE_TEAM)
