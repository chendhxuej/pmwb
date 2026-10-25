"""需求与交付：新增需求分类功能（字典表 + ext 加列 + 预置分类）

背景（需求与交付「需求分类」，2026-10-25 老大拍板）：
  - pmwb_requirement_category：分类字典表（平铺一级，name 唯一，支持启停），
    唯一真相源——工单 ext.category 直接落本表 name 中文名，无 code 列，零转译；
  - pmwb_requirement_ext.category：工单分类落点，String(64) 可空（空=未分类），
    存量工单不回填（禁 ENUM，沿 20261008000001 决策）；
  - 预置 7 类分类基于 77 条真实工单归纳（4/6 字业务口径），
    INSERT ... WHERE NOT EXISTS 幂等，防迁移重放重复插入。

  幂等性：建表/加列/索引/种子均先探测，存在则跳过，可安全重复执行。

Revision ID: 20261026000001
Revises: 20261025000001
Create Date: 2026-10-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20261026000001"
down_revision: Union[str, None] = "20261025000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CAT_TABLE = "pmwb_requirement_category"
EXT_TABLE = "pmwb_requirement_ext"

# 预置分类（基于 2026-10 全量 77 条需求工单归纳，sort_order 10~70）
PRESET_CATEGORIES = [
    ("业务流程优化", "流程改造与跨系统贯通，含接口/字段同步类"),
    ("一线操作提效", "批量操作、查询导出、界面效率类"),
    ("渠道受理赋能", "网格通/营业厅购物车/扫码等渠道受理能力"),
    ("商品体系建设", "资费新增调整、产品供给、议价计费规则"),
    ("BC协同", "BC融合营销、订单协同、商机承接"),
    ("智能应用", "AI 助手、智能化能力"),
    ("数据合规治理", "实名制、权限风控、数据整改与差错修复"),
]


def _has_table(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def _has_column(bind, table: str, column: str) -> bool:
    return column in [c["name"] for c in inspect(bind).get_columns(table)]


def _has_index(bind, table: str, index: str) -> bool:
    return index in [i["name"] for i in inspect(bind).get_indexes(table)]


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, CAT_TABLE):
        op.create_table(
            CAT_TABLE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
            sa.Column("name", sa.String(length=64), nullable=False,
                      comment="分类名称，即工单落库值"),
            sa.Column("sort_order", sa.Integer(), nullable=True,
                      server_default=sa.text("0"), comment="排序号，越小越靠前"),
            sa.Column("enabled", sa.Boolean(), nullable=True, server_default=sa.text("1"),
                      comment="是否启用，停用后不出现在下拉但存量工单保留展示"),
            sa.Column("remark", sa.String(length=255), nullable=True, comment="用途说明，便于后续维护"),
            sa.Column("created_at", sa.DateTime(), nullable=True, comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), nullable=True, comment="更新时间"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", name="uk_req_cat_name"),
            comment="需求分类字典（唯一真相源：工单分类以本表 name 为准）",
        )

    if not _has_column(bind, EXT_TABLE, "category"):
        op.add_column(
            EXT_TABLE,
            sa.Column("category", sa.String(length=64), nullable=True,
                      comment="需求分类（中文名，来自 pmwb_requirement_category）"),
        )
    if not _has_index(bind, EXT_TABLE, "idx_req_category"):
        op.create_index("idx_req_category", EXT_TABLE, ["category"])

    # 预置分类：幂等插入（已有同名则跳过，尊重用户后续改名）
    for name, remark in PRESET_CATEGORIES:
        bind.execute(
            sa.text(
                f"INSERT INTO {CAT_TABLE} (name, sort_order, enabled, remark, created_at, updated_at) "
                "SELECT :name, :sort_order, 1, :remark, NOW(), NOW() "
                f"WHERE NOT EXISTS (SELECT 1 FROM {CAT_TABLE} WHERE name = :name)"
            ),
            {"name": name, "sort_order": (PRESET_CATEGORIES.index((name, remark)) + 1) * 10, "remark": remark},
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_index(bind, EXT_TABLE, "idx_req_category"):
        op.drop_index("idx_req_category", table_name=EXT_TABLE)
    if _has_column(bind, EXT_TABLE, "category"):
        op.drop_column(EXT_TABLE, "category")
    if _has_table(bind, CAT_TABLE):
        op.drop_table(CAT_TABLE)
