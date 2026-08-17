"""重点工作月/周计划字段扩展

为 pmwb_key_work_monthly_plan 与 pmwb_key_work_weekly_plan 增加：
- task_date: 创建日期
- title: 任务标题
- assignee: 责任人
- due_date: 计划完成日期

content 字段继续承载任务描述，comment 调整为"任务描述"。
"""
from alembic import op
import sqlalchemy as sa


revision = "20260817000001"
down_revision = "20260816000002"
branch_labels = None
depends_on = None


_COLUMNS = [
    ("task_date", sa.Date(), True, "创建日期"),
    ("title", sa.String(500), True, "任务标题"),
    ("assignee", sa.String(64), True, "责任人"),
    ("due_date", sa.Date(), True, "计划完成日期"),
]


def _add_columns(table: str):
    for name, col_type, nullable, comment in _COLUMNS:
        op.add_column(
            table,
            sa.Column(name, col_type, nullable=nullable, comment=comment),
        )


def _drop_columns(table: str):
    for name, _, _, _ in reversed(_COLUMNS):
        op.drop_column(table, name)


def upgrade() -> None:
    _add_columns("pmwb_key_work_monthly_plan")
    _add_columns("pmwb_key_work_weekly_plan")

    # 更新 content 注释为"任务描述"（MySQL 通过 modify column 方式）
    op.alter_column(
        "pmwb_key_work_monthly_plan",
        "content",
        existing_type=sa.Text(),
        existing_nullable=True,
        comment="任务描述",
    )
    op.alter_column(
        "pmwb_key_work_weekly_plan",
        "content",
        existing_type=sa.Text(),
        existing_nullable=True,
        comment="任务描述",
    )


def downgrade() -> None:
    op.alter_column(
        "pmwb_key_work_monthly_plan",
        "content",
        existing_type=sa.Text(),
        existing_nullable=True,
        comment="计划内容",
    )
    op.alter_column(
        "pmwb_key_work_weekly_plan",
        "content",
        existing_type=sa.Text(),
        existing_nullable=True,
        comment="计划内容",
    )
    _drop_columns("pmwb_key_work_monthly_plan")
    _drop_columns("pmwb_key_work_weekly_plan")
