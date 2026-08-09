"""knowledge_item_note_type

Revision ID: 20260809000002
Revises: 20260809000001
Create Date: 2026-08-09 19:00:00.000000

NOTE:
- pmwb_knowledge_item 新增 note_type 列（main=业务知识主笔记 / sub=子笔记），支持「系统自动保活每领域唯一主笔记」。
- 存量回填：sub_category='主笔记' 的既有主笔记标记为 note_type='main'，其余默认 'sub'。
- 幂等：列是否已存在、索引是否已存在均做检查，SQLite(测试) 与 MySQL(生产) 均可重复执行。

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260809000002'
down_revision: Union[str, None] = '20260809000001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(bind, table: str, column: str) -> bool:
    return column in [c["name"] for c in sa.inspect(bind).get_columns(table)]


def _index_exists(bind, index_name: str) -> bool:
    return bool(sa.inspect(bind).get_indexes("pmwb_knowledge_item"))


def upgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, "pmwb_knowledge_item", "note_type"):
        op.add_column(
            "pmwb_knowledge_item",
            sa.Column(
                "note_type",
                sa.String(16),
                nullable=False,
                server_default="sub",
                comment="笔记类型：main(业务知识主笔记)/sub(子笔记)",
            ),
        )

    # 存量回填：既有主笔记（sub_category='主笔记'）标记为 main
    op.execute(
        sa.text(
            "UPDATE pmwb_knowledge_item SET note_type='main' "
            "WHERE sub_category = '主笔记' AND (note_type IS NULL OR note_type <> 'main')"
        )
    )
    # 其余 NULL 兜底为 sub（防旧数据 server_default 未生效）
    op.execute(
        sa.text(
            "UPDATE pmwb_knowledge_item SET note_type='sub' WHERE note_type IS NULL"
        )
    )

    # 索引（幂等）
    if not _index_exists(bind, "idx_knowledge_domain_type"):
        op.create_index(
            "idx_knowledge_domain_type",
            "pmwb_knowledge_item",
            ["domain_code", "note_type"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _index_exists(bind, "idx_knowledge_domain_type"):
        op.drop_index("idx_knowledge_domain_type", table_name="pmwb_knowledge_item")
    if _column_exists(bind, "pmwb_knowledge_item", "note_type"):
        op.drop_column("pmwb_knowledge_item", "note_type")
