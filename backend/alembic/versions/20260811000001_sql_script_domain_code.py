"""SQL脚本库补 domain_code + 索引

Revision ID: 20260811000001
Revises: 20260809000003
"""
from alembic import op
import sqlalchemy as sa


revision = '20260811000001'
down_revision = '20260809000003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pmwb_sql_script",
        sa.Column(
            "domain_code",
            sa.String(64),
            nullable=True,
            comment="关联业务领域编码，纳入领域体系与知识检索",
        ),
    )
    op.create_index("idx_sql_domain", "pmwb_sql_script", ["domain_code"])


def downgrade() -> None:
    op.drop_index("idx_sql_domain", table_name="pmwb_sql_script")
    op.drop_column("pmwb_sql_script", "domain_code")
