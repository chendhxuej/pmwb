"""email_records.subject widen to Text (no truncation)

邮件主题此前为 String(500)，长工单标题会被截断甚至导致落库失败。
放开为 Text，确保邮件标题完整（修复邮件预览/发送标题超长丢失问题）。

Revision ID: 20260804000002
Revises: 20260804000001
"""

from alembic import op
import sqlalchemy as sa


revision = "20260804000002"
down_revision = "20260804000001"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "email_records",
        "subject",
        type_=sa.Text(),
        existing_type=sa.String(500),
        existing_nullable=True,
        comment="邮件主题（完整，不截断）",
    )


def downgrade():
    op.alter_column(
        "email_records",
        "subject",
        type_=sa.String(500),
        existing_type=sa.Text(),
        existing_nullable=True,
        comment="邮件主题",
    )
