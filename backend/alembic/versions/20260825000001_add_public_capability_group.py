"""add public capability group and group recharge domain

Revision ID: 20260825000001
Revises: 20260821000002
Create Date: 2026-08-25 10:04:00

新增「公共能力」业务大类（一级），并在其下新增「集团充值」细分业务领域。
幂等设计：仅当 domain_code 不存在时插入，重复执行无副作用。
"""
from alembic import op
import sqlalchemy as sa

revision = "20260825000001"
down_revision = "20260821000002"
branch_labels = None
depends_on = None


def _exists(conn, code: str) -> bool:
    row = conn.execute(
        sa.text("SELECT id FROM pmwb_business_domain WHERE domain_code = :c"),
        {"c": code},
    ).fetchone()
    return row is not None


def upgrade():
    conn = op.get_bind()

    # 1. 新增一级大类「公共能力」（幂等）
    if not _exists(conn, "public-capability"):
        conn.execute(
            sa.text(
                "INSERT INTO pmwb_business_domain "
                "(domain_code, domain_name, domain_group, vault_path, parent_id, sort_order, description, enabled) "
                "VALUES ('public-capability', '公共能力', '公共能力', "
                "'01-业务知识/政企业务知识库/公共能力', NULL, 40, "
                "'政企公共能力建设与运营（充值/计费/统一能力等）', 1)"
            )
        )

    # 2. 新增二级细分「集团充值」（挂在 public-capability 下）
    if not _exists(conn, "group-recharge"):
        # 先查出父领域 id
        row = conn.execute(
            sa.text("SELECT id FROM pmwb_business_domain WHERE domain_code = 'public-capability'")
        ).fetchone()
        if row:
            conn.execute(
                sa.text(
                    "INSERT INTO pmwb_business_domain "
                    "(domain_code, domain_name, domain_group, vault_path, parent_id, sort_order, description, enabled) "
                    "VALUES ('group-recharge', '集团充值', '公共能力', "
                    "'01-业务知识/政企业务知识库/公共能力/集团充值', :pid, 41, '集团客户充值业务', 1)"
                ).bindparams(pid=row[0])
            )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM pmwb_business_domain WHERE domain_code IN ('group-recharge', 'public-capability')")
    )
