"""会议附件：pmwb_meeting 加 attachments 元信息列

- 元数据 JSON 数组 [{name, size, uploaded_at}] 落 pmwb_meeting.attachments；
- 文件实体落 settings.MEETING_ATTACHMENT_DIR/{会议主键}/（项目内 data 目录）；
- 唯一实现 services/meeting_attachment.py（上传=同名替换，删除=文件+元数据同删）。

⚠ 项目 alembic 多 head（坏壳 20260908105939 遗留），执行须显式指定：
  alembic upgrade 20261110000001

Revision ID: 20261110000001
Revises: 20261104000008
Create Date: 2026-11-10
"""
from alembic import op
import sqlalchemy as sa

revision = "20261110000001"
down_revision = "20261104000008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pmwb_meeting",
        sa.Column("attachments", sa.Text, comment="附件元信息(JSON 数组)"),
    )


def downgrade() -> None:
    op.drop_column("pmwb_meeting", "attachments")
