"""新增 pmwb_active_optimization_req：主动优化工单「关联需求文号」一对多

背景（2026-10-16）：
  主动优化工单原先只能挂**一个**需求文号（pmwb_active_optimization.req_id 单列）。
  实际业务中一条优化建议往往源自多个需求，单值不够用，故拆出关联表支持一对多。

  职责划分（务必区分，别搞混）：
    - pmwb_active_optimization_req：**关联落地表**，一张工单可挂 N 个文号，
      uk_opt_req(opt_id, req_id) 是防重复的唯一真相源。
    - pmwb_active_optimization.req_id：**保留但废弃写入**，降级为历史兼容镜像
      （迁移幂等源 + 邮件模板变量兼容 + 规避 service.update 无法清空字段的历史坑）。
      **禁止 DROP 该列**。

  口径铁律：req_id 必须存在于需求宇宙（SELECT DISTINCT req_id FROM sent_emails），
  校验唯一实现在 services/active_optimization.py::_replace_req_links。

  存量迁移：本迁移会把 pmwb_active_optimization.req_id 的非空值灌入关联表，
  用 NOT EXISTS 探测保证幂等，可安全重复执行。

  ⚠ 多 head 环境提示：本仓库存在多个 head（vendor_dev / high_level_track 及一个
  revision 为 '%(rev)s' 占位的历史脏文件），`alembic upgrade head` 不可用。
  请显式执行：alembic upgrade 20261017000001
  应用启动时 main.py 也会 Base.metadata.create_all，本迁移供显式迁移链使用。

Revision ID: 20261017000001
Revises: 20261016000001
Create Date: 2026-10-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision: str = "20261017000001"
down_revision: Union[str, None] = "20261016000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "pmwb_active_optimization_req"
SRC = "pmwb_active_optimization"


def _has_table(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, TABLE):
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
            sa.Column("opt_id", sa.Integer(), nullable=False, comment="主动优化工单ID"),
            sa.Column("req_id", sa.String(length=255), nullable=False,
                      comment="关联需求文号（须存在于 sent_emails 需求宇宙）"),
            sa.Column("req_name", sa.String(length=500), nullable=True,
                      comment="需求名称冗余快照（仅展示，不参与校验）"),
            sa.Column("created_by", sa.String(length=64), nullable=True, comment="创建人"),
            sa.Column("created_at", sa.DateTime(), nullable=True, comment="创建时间"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("opt_id", "req_id", name="uk_opt_req"),
            comment="主动优化工单与需求文号关联表（一对多）",
        )
        op.create_index("idx_aor_req_id", TABLE, ["req_id"])

    # 存量迁移：把工单主表 req_id 灌入关联表（NOT EXISTS 保证幂等）
    if _has_table(bind, SRC):
        bind.execute(
            text(
                f"""
                INSERT INTO {TABLE} (opt_id, req_id, req_name, created_by, created_at)
                SELECT o.id,
                       TRIM(o.req_id),
                       (SELECT s.req_name FROM sent_emails s
                        WHERE s.req_id = TRIM(o.req_id) LIMIT 1),
                       NULL,
                       NOW()
                FROM {SRC} o
                WHERE o.req_id IS NOT NULL
                  AND TRIM(o.req_id) <> ''
                  AND NOT EXISTS (
                        SELECT 1 FROM {TABLE} r
                        WHERE r.opt_id = o.id AND r.req_id = TRIM(o.req_id)
                  )
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, TABLE):
        op.drop_table(TABLE)
