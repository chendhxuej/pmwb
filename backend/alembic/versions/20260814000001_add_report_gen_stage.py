"""add gen_stage/gen_error_msg to pmwb_work_report

AI总结改为异步生成后，需要记录后台任务的阶段（collecting/llm/assembling）
与失败原因，供前端轮询展示进度与兜底恢复僵尸任务。
"""
from alembic import op
import sqlalchemy as sa


revision = "20260814000001"
down_revision = "20260813000001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "pmwb_work_report",
        sa.Column(
            "gen_stage",
            sa.String(40),
            nullable=True,
            comment="异步生成阶段: collecting/llm/assembling/done",
        ),
    )
    op.add_column(
        "pmwb_work_report",
        sa.Column(
            "gen_error_msg",
            sa.Text(),
            nullable=True,
            comment="异步生成失败原因",
        ),
    )


def downgrade():
    op.drop_column("pmwb_work_report", "gen_error_msg")
    op.drop_column("pmwb_work_report", "gen_stage")
