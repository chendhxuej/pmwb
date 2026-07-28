"""add pmwb_role table for role/identity definitions

Revision ID: 20260727_add_pmwb_role
Create Date: 2026-07-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260727_add_pmwb_role"
down_revision: Union[str, None] = "20260727_initial_master"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pmwb_role",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("name", sa.String(64), nullable=False, comment="角色名称（如：产品经理）"),
        sa.Column("sort", sa.Integer(), server_default="0", comment="排序号"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1", comment="是否启用"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), comment="创建时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        comment="人员中台-身份/角色定义表",
    )


def downgrade() -> None:
    op.drop_table("pmwb_role")
