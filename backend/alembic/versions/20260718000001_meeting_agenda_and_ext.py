"""会议模块扩展：议题表 + 召集人/参会注意点 + 行动项分类模板

Revision ID: 20260718000001
Revises: 20260713000001
Create Date: 2026-07-18 21:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260718000001"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pmwb_meeting: 新增 召集人 / 参会注意点
    op.add_column(
        "pmwb_meeting",
        sa.Column("convener", sa.String(64), nullable=True, comment="召集人"),
    )
    op.add_column(
        "pmwb_meeting",
        sa.Column("attendee_notes", sa.Text(), nullable=True, comment="参会注意点"),
    )

    # pmwb_meeting_agenda: 新建议题表
    op.create_table(
        "pmwb_meeting_agenda",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("meeting_id", sa.Integer(), nullable=False, comment="关联会议ID"),
        sa.Column("seq", sa.Integer(), server_default="1", comment="议题序号（用于排序）"),
        sa.Column("topic", sa.String(255), nullable=False, comment="议题标题"),
        sa.Column("conclusion", sa.Text(), nullable=True, comment="商讨结论"),
        sa.Column("division", sa.Text(), nullable=True, comment="分工说明"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.ForeignKeyConstraint(["meeting_id"], ["pmwb_meeting.id"]),
        sa.PrimaryKeyConstraint("id"),
        comment="会议议题表",
    )
    op.create_index("idx_agenda_meeting_id", "pmwb_meeting_agenda", ["meeting_id"])

    # pmwb_meeting_action: 新增 分类 / 模板
    op.add_column(
        "pmwb_meeting_action",
        sa.Column(
            "category",
            sa.String(64),
            nullable=True,
            comment="待办分类（对应 pmwb_todo.category）：requirement/ticket/operation/meeting/study/other",
        ),
    )
    op.add_column(
        "pmwb_meeting_action",
        sa.Column("template", sa.String(128), nullable=True, comment="Obsidian 待办模板名（仅元数据标签）"),
    )


def downgrade() -> None:
    op.drop_column("pmwb_meeting_action", "template")
    op.drop_column("pmwb_meeting_action", "category")
    op.drop_index("idx_agenda_meeting_id", table_name="pmwb_meeting_agenda")
    op.drop_table("pmwb_meeting_agenda")
    op.drop_column("pmwb_meeting", "attendee_notes")
    op.drop_column("pmwb_meeting", "convener")
    # 注：agenda 表不设 UNIQUE(meeting_id)，一个会议可有多个议题
