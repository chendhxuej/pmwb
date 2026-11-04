"""运营工单增加客诉关联工单结构化明细列

背景（老大 2026-11-04 反馈）：问题→建运营工单时，关联投诉工单明细原先
全部拼成纯文本塞进 situation_desc，「糊在一起」。改为：
  - situation_desc 只存「情况说明」总结（自动生成 + 手工整合，可读）；
  - 明细（工单号/投诉内容/核查过程/AI 分析）存 context_tickets JSON 数组，
    工单详情页按表格渲染、催办/同步邮件按 markdown 表格生成。

Revision ID: 20261104000006
Revises: 20261104000005
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104000006"
down_revision = "20261104000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pmwb_operation_issue",
        sa.Column("context_tickets", sa.Text(), nullable=True,
                   comment="客诉关联投诉工单明细(JSON数组，由建单联动写入)"),
    )


def downgrade() -> None:
    op.drop_column("pmwb_operation_issue", "context_tickets")
