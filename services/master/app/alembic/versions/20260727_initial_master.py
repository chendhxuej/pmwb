"""initial master schema: pmwb_org + pmwb_staff

Revision ID: 20260727_initial_master
Create Date: 2026-07-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260727_initial_master"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pmwb_org",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("name", sa.String(128), nullable=False, comment="组织/团队名称"),
        sa.Column("description", sa.String(512), comment="组织描述（可空）"),
        sa.Column("sort", sa.Integer(), server_default="0", comment="排序号"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1", comment="是否启用"),
        sa.Column("source_trace", sa.String(64), comment="数据来源"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), comment="创建时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        comment="人员中台-组织表",
    )

    op.create_table(
        "pmwb_staff",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("name", sa.String(64), nullable=False, comment="姓名"),
        sa.Column("org_id", sa.Integer(), nullable=False, comment="所属组织ID"),
        sa.Column("email", sa.String(255), comment="邮箱"),
        sa.Column("phone", sa.String(64), comment="电话"),
        sa.Column("role_hint", sa.String(128), comment="角色/职责备注"),
        sa.Column("sort", sa.Integer(), server_default="0", comment="排序号"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1", comment="是否启用"),
        sa.Column("source_trace", sa.String(64), comment="数据来源"),
        sa.Column("legacy_id", sa.String(255), comment="原数据源记录ID"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), comment="更新时间"),
        sa.ForeignKeyConstraint(["org_id"], ["pmwb_org.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "org_id", name="uk_staff_name_org"),
        comment="人员中台-人员表",
    )

    op.create_index("idx_staff_org", "pmwb_staff", ["org_id"])


def downgrade() -> None:
    op.drop_table("pmwb_staff")
    op.drop_table("pmwb_org")
