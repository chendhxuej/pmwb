"""需求工单 1:1 单向关联表

- pmwb_requirement_link：主工单 → 从工单，两端各自唯一。
- 状态镜像由 RequirementService.update_ext 单向同步一层，不写第二份状态真相源。

⚠ 项目 alembic 存在多 head（坏壳 20260908105939），执行须显式指定：
  alembic upgrade 20261126000001

Revision ID: 20261126000001
Revises: 20261120000001
Create Date: 2026-11-26
"""
from alembic import op
import sqlalchemy as sa

revision = "20261126000001"
down_revision = "20261120000001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pmwb_requirement_link",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("req_id", sa.String(64), nullable=False, comment="主需求工单文号"),
        sa.Column("linked_req_id", sa.String(64), nullable=False, comment="关联需求工单文号（从）"),
        sa.Column("created_by", sa.String(64), comment="关联设置人"),
        sa.Column("created_at", sa.DateTime(), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), comment="更新时间"),
        sa.UniqueConstraint("req_id", name="uk_req_link_owner"),
        sa.UniqueConstraint("linked_req_id", name="uk_req_link_target"),
        mysql_charset="utf8mb4",
        comment="需求工单 1:1 单向关联",
    )


def downgrade():
    op.drop_table("pmwb_requirement_link")
