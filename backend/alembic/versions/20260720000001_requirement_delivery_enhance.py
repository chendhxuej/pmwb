"""需求与交付模块增强：扩展表可编辑字段 + 用户故事表

Revision ID: 20260720000001
Revises: 20260718000001
Create Date: 2026-07-20 13:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260720000001"
down_revision: Union[str, None] = "20260718000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pmwb_requirement_ext: 新增可编辑覆盖字段
    op.add_column(
        "pmwb_requirement_ext",
        sa.Column("req_name", sa.String(500), nullable=True, comment="需求名称（可编辑覆盖）"),
    )
    op.add_column(
        "pmwb_requirement_ext",
        sa.Column("background", sa.Text(), nullable=True, comment="需求背景（可编辑覆盖）"),
    )
    op.add_column(
        "pmwb_requirement_ext",
        sa.Column("description", sa.Text(), nullable=True, comment="需求描述（可编辑覆盖）"),
    )
    op.add_column(
        "pmwb_requirement_ext",
        sa.Column("clarification", sa.Text(), nullable=True, comment="澄清内容（可编辑覆盖）"),
    )
    op.add_column(
        "pmwb_requirement_ext",
        sa.Column("system_name", sa.String(255), nullable=True, comment="涉及系统（可编辑覆盖）"),
    )
    op.add_column(
        "pmwb_requirement_ext",
        sa.Column("sa_name", sa.String(255), nullable=True, comment="SA（可编辑覆盖）"),
    )

    # pmwb_user_story: 用户故事持久化表
    op.create_table(
        "pmwb_user_story",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("req_id", sa.String(64), nullable=False, comment="需求编号"),
        sa.Column("seq", sa.Integer(), server_default="1", comment="故事序号"),
        sa.Column("title", sa.String(500), nullable=True, comment="故事标题"),
        sa.Column("desc", sa.Text(), nullable=True, comment="故事描述"),
        sa.Column("scene", sa.Text(), nullable=True, comment="故事场景"),
        sa.Column("acceptance", sa.Text(), nullable=True, comment="验收标准(JSON数组)"),
        sa.Column("finalized", sa.Integer(), server_default="0", comment="是否已定稿(0:草稿 1:定稿)"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("req_id", "seq", name="uk_user_story_req_seq"),
        sa.Index("idx_user_story_req_id", "req_id"),
        comment="需求用户故事表",
    )


def downgrade() -> None:
    op.drop_table("pmwb_user_story")
    op.drop_column("pmwb_requirement_ext", "sa_name")
    op.drop_column("pmwb_requirement_ext", "system_name")
    op.drop_column("pmwb_requirement_ext", "clarification")
    op.drop_column("pmwb_requirement_ext", "description")
    op.drop_column("pmwb_requirement_ext", "background")
    op.drop_column("pmwb_requirement_ext", "req_name")
