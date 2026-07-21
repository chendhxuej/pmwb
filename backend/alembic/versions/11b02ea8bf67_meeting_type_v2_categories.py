"""meeting_type_v2_categories

会议类型重新定义为：需求讨论、问题分析、内部例会、外部对接、党会、集团会议、其他。

Revision ID: 11b02ea8bf67
Revises: d043b45ff51e
Create Date: 2026-07-21 17:32:17.955020

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "11b02ea8bf67"
down_revision: Union[str, None] = "d043b45ff51e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_TO_NEW = {
    "requirement_review": "requirement_discussion",
    "project_weekly": "internal_regular",
    "troubleshooting": "problem_analysis",
    "training": "other",
}

NEW_TO_OLD = {
    "requirement_discussion": "requirement_review",
    "problem_analysis": "troubleshooting",
    "internal_regular": "project_weekly",
    "external_sync": "other",
    "party_meeting": "other",
    "group_meeting": "other",
    "other": "other",
}


def _migrate_values(mapping: dict) -> None:
    """按 mapping 批量改写 pmwb_meeting.meeting_type 存量值。"""
    cases = " ".join(
        f"WHEN '{old}' THEN '{new}'" for old, new in mapping.items()
    )
    op.execute(
        f"""
        UPDATE pmwb_meeting
        SET meeting_type = CASE meeting_type
            {cases}
            ELSE meeting_type
        END
        """
    )


def upgrade() -> None:
    # 1. 将列类型从 MySQL ENUM 改为 VARCHAR(32)，避免新值被枚举限制拒绝。
    op.alter_column(
        "pmwb_meeting",
        "meeting_type",
        existing_type=mysql.ENUM(
            "requirement_review",
            "project_weekly",
            "troubleshooting",
            "training",
            "other",
            collation="utf8mb4_unicode_ci",
        ),
        type_=sa.String(length=32),
        existing_comment="会议类型",
        existing_nullable=True,
        existing_server_default=sa.text("'other'"),
    )

    # 2. 将旧类型值迁移到新的 7 类定义。
    _migrate_values(OLD_TO_NEW)


def downgrade() -> None:
    # 1. 将新类型值回退到旧枚举（多对一映射到最接近的旧值）。
    _migrate_values(NEW_TO_OLD)

    # 2. 恢复为旧的 ENUM 类型。
    op.alter_column(
        "pmwb_meeting",
        "meeting_type",
        existing_type=sa.String(length=32),
        type_=mysql.ENUM(
            "requirement_review",
            "project_weekly",
            "troubleshooting",
            "training",
            "other",
            collation="utf8mb4_unicode_ci",
        ),
        existing_comment="会议类型",
        existing_nullable=True,
        existing_server_default=sa.text("'other'"),
    )
