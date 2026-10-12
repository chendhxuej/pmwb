"""sent_emails 增加 origin 列：区分插件抓取与工作台手工新建

背景（需求与交付模块「手工新建需求工单」能力，2026-10-12）：
  需求宇宙 = `sent_emails` 去重 req_id，此前只有 Chrome 插件写入（邮件行）。
  新增手工新建能力后，两类记录共用同一张表以沿用唯一口径，需要一列标记来源：
    - plugin：浏览器插件抓取的邮件行（默认，历史数据全部回填为该值）
    - manual：老大在工作台「需求与交付」页手工录入的行

  该列同时承载删除语义：`delete_requirement` 仅对 origin='manual' 的源行做真删，
  plugin 行保持只读保留，避免「删完立刻从需求宇宙复活」。

幂等性：upgrade/downgrade 均先探测列是否存在，存在则跳过，可安全重复执行。

Revision ID: 20261012000002
Revises: 20261012000001
Create Date: 2026-10-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20261012000002"
down_revision: Union[str, None] = "20261012000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "sent_emails"
COLUMN = "origin"
DEFAULT = "plugin"
COMMENT = "来源：plugin(浏览器插件抓取的邮件) / manual(工作台手工新建)"


def _has_column(bind) -> bool:
    insp = inspect(bind)
    if TABLE not in insp.get_table_names():
        return False
    return any(col["name"] == COLUMN for col in insp.get_columns(TABLE))


def upgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind):
        return  # 幂等跳过
    op.add_column(
        TABLE,
        sa.Column(
            COLUMN,
            sa.String(length=16),
            nullable=False,
            server_default=sa.text(f"'{DEFAULT}'"),
            comment=COMMENT,
        ),
    )
    # 历史行回填为插件来源（server_default 已覆盖，此处兜底 NULL 脏值）
    op.execute(
        sa.text(f"UPDATE {TABLE} SET {COLUMN} = '{DEFAULT}' WHERE {COLUMN} IS NULL OR {COLUMN} = ''")
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind):
        return  # 幂等跳过
    op.drop_column(TABLE, COLUMN)
