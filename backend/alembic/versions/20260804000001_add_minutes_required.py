"""add minutes_required to pmwb_meeting

支持会议「无需纪要」状态：开完会后不需要记录纪要时置为 False，从待归档列表与待写纪要统计中移除。

Revision ID: 20260804000001
Revises: 20260801000002
"""
from alembic import op
import sqlalchemy as sa

revision = "20260804000001"
down_revision = "20260801000002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "pmwb_meeting",
        sa.Column(
            "minutes_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
            comment="是否需要纪要（开完会无需记录纪要时置为 False）",
        ),
    )


def downgrade():
    op.drop_column("pmwb_meeting", "minutes_required")
