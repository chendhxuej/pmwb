"""kc4-2: pmwb_requirement_ext 增加产商品/业务流程变更标记

用于主笔记「业务事实区」的保守回写策略：仅 status='closed' 且勾选对应标记的需求，
才允许回写主笔记的产商品体系 / 业务流程自动区，避免草稿或未上线需求污染业务权威源。

存量数据默认 0（不变更），不影响既有逻辑。
"""
from alembic import op
import sqlalchemy as sa


revision = "20260812000002"
down_revision = "20260812000001"
branch_labels = None
depends_on = None

TABLE = "pmwb_requirement_ext"


def _existing_columns(conn) -> set:
    insp = sa.inspect(conn)
    return {c["name"] for c in insp.get_columns(TABLE)}


def upgrade() -> None:
    conn = op.get_bind()
    cols = _existing_columns(conn)

    if "product_changed" not in cols:
        op.add_column(
            TABLE,
            sa.Column(
                "product_changed",
                sa.Integer(),
                nullable=True,
                server_default="0",
                comment="本需求是否涉及产商品体系变更(1是)，用于主笔记产商品区保守回写",
            ),
        )
    if "process_changed" not in cols:
        op.add_column(
            TABLE,
            sa.Column(
                "process_changed",
                sa.Integer(),
                nullable=True,
                server_default="0",
                comment="本需求是否涉及业务流程变更(1是)，用于主笔记业务流程区保守回写",
            ),
        )

    # 存量补 0，保证聚合查询不受 NULL 影响
    conn.execute(
        sa.text(
            f"UPDATE {TABLE} SET product_changed = 0 WHERE product_changed IS NULL"
        )
    )
    conn.execute(
        sa.text(
            f"UPDATE {TABLE} SET process_changed = 0 WHERE process_changed IS NULL"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    cols = _existing_columns(conn)
    if "process_changed" in cols:
        op.drop_column(TABLE, "process_changed")
    if "product_changed" in cols:
        op.drop_column(TABLE, "product_changed")
