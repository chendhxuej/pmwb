"""knowledge_link_table_fk

Revision ID: 20260809000001
Revises: 945f101c2ac0
Create Date: 2026-08-09 13:45:00.000000

NOTE:
- 本迁移幂等补建 pmwb_knowledge_link 表与约束。
- 存量环境：表已由 create_all 建立（含列与唯一索引），此处仅补 FK 与缺失索引；
- 全新环境：完整建表（含 FK 与全部索引）。
- 补 FK 前已验证存量 3 行数据引用均有效（无孤儿行），可安全建立外键。

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260809000001'
down_revision: Union[str, None] = '945f101c2ac0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "pmwb_knowledge_link"):
        op.create_table(
            "pmwb_knowledge_link",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
            sa.Column(
                "knowledge_item_id",
                sa.Integer(),
                nullable=False,
                comment="关联知识条目索引ID（指向 pmwb_knowledge_item.id）",
            ),
            sa.Column(
                "source_type",
                sa.String(length=64),
                nullable=False,
                comment="关联对象类型：requirement/ticket/operation/meeting/deliverable/key_work",
            ),
            sa.Column(
                "source_id",
                sa.String(length=255),
                nullable=False,
                comment="关联对象业务ID（req_id / 工单id / 会议id / 运营id 等）",
            ),
            sa.Column(
                "link_type",
                sa.String(length=32),
                nullable=True,
                comment="链接类型：main(主笔记)/sub(子笔记)/deliverable(交付物)",
            ),
            sa.Column("domain_code", sa.String(length=64), nullable=True, comment="冗余领域编码，便于按领域查询"),
            sa.Column("note", sa.Text(), nullable=True, comment="关联说明"),
            sa.Column("created_at", sa.DateTime(), nullable=True, comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), nullable=True, comment="更新时间"),
            sa.ForeignKeyConstraint(
                ["knowledge_item_id"],
                ["pmwb_knowledge_item.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "knowledge_item_id", "source_type", "source_id",
                name="idx_kl_item_source",
            ),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_comment="知识笔记与过程性对象多对多关联表",
        )
        op.create_index("idx_kl_source", "pmwb_knowledge_link", ["source_type", "source_id"])
        op.create_index("idx_kl_domain", "pmwb_knowledge_link", ["domain_code"])
    else:
        # 存量环境：补缺失的索引与外键（列已存在则不动）
        insp = sa.inspect(bind)
        idxs = {i["name"] for i in insp.get_indexes("pmwb_knowledge_link")}
        ucs = {u["name"] for u in insp.get_unique_constraints("pmwb_knowledge_link")}
        if "idx_kl_source" not in idxs:
            op.create_index("idx_kl_source", "pmwb_knowledge_link", ["source_type", "source_id"])
        if "idx_kl_domain" not in idxs:
            op.create_index("idx_kl_domain", "pmwb_knowledge_link", ["domain_code"])
        if "idx_kl_item_source" not in ucs and "idx_kl_item_source" not in idxs:
            op.create_unique_constraint(
                "idx_kl_item_source",
                "pmwb_knowledge_link",
                ["knowledge_item_id", "source_type", "source_id"],
            )
        fks = insp.get_foreign_keys("pmwb_knowledge_link")
        has_item_fk = any(fk.get("referred_table") == "pmwb_knowledge_item" for fk in fks)
        if not has_item_fk:
            op.create_foreign_key(
                "fk_kl_knowledge_item",
                "pmwb_knowledge_link",
                "pmwb_knowledge_item",
                ["knowledge_item_id"],
                ["id"],
                ondelete="CASCADE",
            )


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "pmwb_knowledge_link"):
        return
    insp = sa.inspect(bind)
    fks = insp.get_foreign_keys("pmwb_knowledge_link")
    if any(fk.get("name") == "fk_kl_knowledge_item" for fk in fks):
        op.drop_constraint("fk_kl_knowledge_item", "pmwb_knowledge_link", type_="foreignkey")
    idxs = {i["name"] for i in insp.get_indexes("pmwb_knowledge_link")}
    if "idx_kl_domain" in idxs:
        op.drop_index("idx_kl_domain", table_name="pmwb_knowledge_link")
    if "idx_kl_source" in idxs:
        op.drop_index("idx_kl_source", table_name="pmwb_knowledge_link")
