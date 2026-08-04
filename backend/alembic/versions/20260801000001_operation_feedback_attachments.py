"""运营工单：增加计划完成时间、处理结果反馈、附件字段。

- go_live_date: 计划完成时间（原前端列表已展示但后端无列，导致无法保存）
- result_feedback: 处理结果反馈（支持后续编辑更新填写）
- attachments: 附件元信息（JSON 数组字符串）
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260801000001"
down_revision: str = "20260727000001"
branch_labels: tuple = None
depends_on: tuple = None


def upgrade() -> None:
    op.add_column(
        "pmwb_operation_issue",
        sa.Column("go_live_date", sa.Date(), nullable=True, comment="计划完成时间"),
    )
    op.add_column(
        "pmwb_operation_issue",
        sa.Column("result_feedback", sa.Text(), nullable=True, comment="处理结果反馈"),
    )
    op.add_column(
        "pmwb_operation_issue",
        sa.Column("attachments", sa.Text(), nullable=True, comment="附件元信息(JSON 数组)"),
    )


def downgrade() -> None:
    op.drop_column("pmwb_operation_issue", "attachments")
    op.drop_column("pmwb_operation_issue", "result_feedback")
    op.drop_column("pmwb_operation_issue", "go_live_date")
