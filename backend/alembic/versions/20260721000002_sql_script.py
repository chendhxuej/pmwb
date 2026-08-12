"""SQL脚本库：pmwb_sql_script 表。

归档常用业务统计脚本：脚本说明、SQL、创建时间、输出字段样例(JSON)。
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260721000002"
down_revision: str = "20260721000001"
branch_labels: tuple = None
depends_on: tuple = None


def upgrade() -> None:
    op.create_table(
        "pmwb_sql_script",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("script_no", sa.String(64), nullable=False, comment="脚本编号 SQL-YYYYMMDD-XXX"),
        sa.Column("title", sa.String(500), nullable=False, comment="脚本说明/名称"),
        sa.Column("category", sa.String(64), nullable=True, comment="业务线/分类（可空，允许自定义）"),
        sa.Column("description", sa.Text(), nullable=True, comment="补充说明"),
        sa.Column("sql_text", sa.Text(), nullable=False, comment="SQL 文本"),
        sa.Column("output_fields", sa.Text(), nullable=True, comment="输出字段样例(JSON数组: name/type/desc)"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("script_no"),
        sa.Index("idx_sql_category", "category"),
        comment="SQL脚本库表",
    )


def downgrade() -> None:
    op.drop_table("pmwb_sql_script")
