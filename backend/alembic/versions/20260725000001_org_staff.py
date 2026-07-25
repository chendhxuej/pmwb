"""基础数据：pmwb_org 组织表 + pmwb_staff 人员表。

全站选人组件（责任人/负责人/参会人等）的统一数据源。
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260725000001"
down_revision: str = "89c1d2bf42c5"
branch_labels: tuple = None
depends_on: tuple = None


def upgrade() -> None:
    op.create_table(
        "pmwb_org",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("name", sa.String(128), nullable=False, comment="组织/团队名称"),
        sa.Column("sort", sa.Integer(), nullable=True, server_default="0", comment="排序号（小的在前）"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1"), comment="是否启用"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        comment="基础数据-组织表",
    )
    op.create_table(
        "pmwb_staff",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("name", sa.String(64), nullable=False, comment="姓名"),
        sa.Column("org_id", sa.Integer(), nullable=False, comment="所属组织ID"),
        sa.Column("email", sa.String(255), nullable=True, comment="邮箱（可空）"),
        sa.Column("phone", sa.String(64), nullable=True, comment="电话（可空）"),
        sa.Column("role_hint", sa.String(128), nullable=True, comment="角色/职责备注（可空）"),
        sa.Column("sort", sa.Integer(), nullable=True, server_default="0", comment="排序号（小的在前）"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1"), comment="是否启用"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["pmwb_org.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("name", "org_id", name="uk_staff_name_org"),
        sa.Index("idx_staff_org", "org_id"),
        comment="基础数据-人员表",
    )


def downgrade() -> None:
    op.drop_table("pmwb_staff")
    op.drop_table("pmwb_org")
