"""pmwb_research_issue.sub_type ENUM → VARCHAR(32)：支持新增调研子类零迁移

背景（一线调研模块「淮安订单中心调研」子类扩容）：
  `pmwb_research_issue.sub_type` 原为 MySQL 原生 ENUM('leader_research','frontline_station')，
  每新增一个调研子类都必须 ALTER TABLE 改枚举，与状态列「String(32) + 常量校验」的
  既有约定（迁移 20261008000001）不一致。
  本迁移把该列统一改为 VARCHAR(32)，合法值校验下沉到
  `backend/schemas/research.py::ResearchSubType` 与各展示层映射。

写法参照 alembic/versions/20261008000001_status_columns_enum_to_string.py。
幂等性：upgrade/downgrade 均先探测当前列类型，已是目标类型则跳过，可安全重复执行。

Revision ID: 20261012000001
Revises: 20261008000001
Create Date: 2026-10-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20261012000001"
down_revision: Union[str, None] = "20261008000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "pmwb_research_issue"
COLUMN = "sub_type"
OLD_VALUES = ("leader_research", "frontline_station")
DEFAULT = "leader_research"
COMMENT = "子类：领导调研/一线驻点/淮安订单中心调研"


def _current_col(bind):
    """返回 sub_type 列的 {type_str, comment}；表/列不存在返回 None。"""
    insp = inspect(bind)
    if TABLE not in insp.get_table_names():
        return None
    for col in insp.get_columns(TABLE):
        if col["name"] == COLUMN:
            return {"type": str(col["type"]).lower(), "comment": col.get("comment") or ""}
    return None


def _alter(bind, to_varchar: bool):
    info = _current_col(bind)
    if info is None:
        return  # 表/列不存在 → 跳过
    cur = info["type"]
    is_varchar = "char" in cur
    if to_varchar and is_varchar:
        return  # 已是 VARCHAR → 幂等跳过
    if (not to_varchar) and cur.startswith("enum"):
        return  # 已是 ENUM → 幂等跳过
    existing = sa.Enum(*OLD_VALUES) if to_varchar else sa.String(length=32)
    target = sa.String(length=32) if to_varchar else sa.Enum(*OLD_VALUES)
    op.alter_column(
        TABLE,
        COLUMN,
        existing_type=existing,
        type_=target,
        existing_nullable=True,
        existing_server_default=sa.text(f"'{DEFAULT}'"),
        server_default=sa.text(f"'{DEFAULT}'"),
        existing_comment=info["comment"] or COMMENT,
        comment=COMMENT,
    )


def upgrade() -> None:
    _alter(op.get_bind(), to_varchar=True)


def downgrade() -> None:
    """回退为 ENUM。若库中已写入 ENUM 之外的新子类值（如 huaian_order_center），
    MySQL 严格模式下会失败，需先清理这些值——属有损回退。"""
    _alter(op.get_bind(), to_varchar=False)
