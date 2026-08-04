"""meeting agenda add background field

Revision ID: 20260801000002
Revises: 20260801000001
"""

from alembic import op
import sqlalchemy as sa


revision = "20260801000002"
down_revision = "20260801000001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "pmwb_meeting_agenda",
        sa.Column("background", sa.Text(), nullable=True, comment="议题背景说明"),
    )


def downgrade():
    op.drop_column("pmwb_meeting_agenda", "background")
