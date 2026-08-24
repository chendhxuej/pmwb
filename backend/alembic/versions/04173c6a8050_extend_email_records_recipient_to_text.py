"""extend_email_records_recipient_to_text

Revision ID: 04173c6a8050
Revises: 5899b666a361
Create Date: 2026-08-24 10:07:15.464126

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '04173c6a8050'
down_revision: Union[str, None] = '5899b666a361'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 会议通知等多收件人场景下，邮箱地址拼接后易超过 255 字符，导致 INSERT 失败并回滚 500。
    # 改为 Text 与 work_report.recipient 保持一致，避免未来再次触发 Data too long。
    op.alter_column(
        'email_records',
        'recipient',
        existing_type=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=255),
        type_=sa.Text(),
        existing_comment='收件人邮箱',
        comment='收件人邮箱（逗号分隔，多个邮箱可能超长）',
        existing_nullable=True,
    )
    op.alter_column(
        'email_records',
        'recipient_name',
        existing_type=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=255),
        type_=sa.Text(),
        existing_comment='收件人姓名',
        comment='收件人姓名（逗号分隔，可能超长）',
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'email_records',
        'recipient',
        existing_type=sa.Text(),
        type_=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=255),
        existing_comment='收件人邮箱（逗号分隔，多个邮箱可能超长）',
        comment='收件人邮箱',
        existing_nullable=True,
    )
    op.alter_column(
        'email_records',
        'recipient_name',
        existing_type=sa.Text(),
        type_=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=255),
        existing_comment='收件人姓名（逗号分隔，可能超长）',
        comment='收件人姓名',
        existing_nullable=True,
    )
