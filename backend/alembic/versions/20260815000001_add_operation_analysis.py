"""add pmwb_operation_analysis table

主动运营分析工单明细表：承接分析长文本与5维度结果，1:1 关联运营工单
(pmwb_operation_issue)。分析工单沿用 category=prod（展示名改为「主动运营分析」），
遗留任务经导入自动建为 category=task 的人员代办任务工单。
"""
from alembic import op
import sqlalchemy as sa


revision = "20260815000001"
down_revision = "20260814000002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pmwb_operation_analysis",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "issue_id",
            sa.Integer(),
            sa.ForeignKey("pmwb_operation_issue.id"),
            nullable=False,
            comment="关联运营工单ID",
        ),
        sa.Column("topic_name", sa.String(length=255), comment="课题名称"),
        sa.Column("analyst_team", sa.String(length=128), comment="运营团队"),
        sa.Column("analyst_name", sa.String(length=128), comment="运营人员姓名"),
        sa.Column("domain_code", sa.String(length=64), comment="关联业务领域编码"),
        sa.Column("background", sa.Text(), comment="课题背景说明"),
        sa.Column("scenario", sa.Text(), comment="操作场景介绍"),
        sa.Column("biz_flow", sa.Text(), comment="业务流程梳理"),
        sa.Column("biz_rule", sa.Text(), comment="业务规则梳理"),
        sa.Column("monitoring", sa.Text(), comment="业务监控梳理"),
        sa.Column("analysis_goal", sa.Text(), comment="本次分析目标"),
        sa.Column("data_analysis", sa.Text(), comment="数据分析过程"),
        sa.Column("result_flow", sa.Text(), comment="分析结果-流程优化方面"),
        sa.Column("result_rule", sa.Text(), comment="分析结果-规则优化方面"),
        sa.Column("result_model", sa.Text(), comment="分析结果-数据模型方面"),
        sa.Column("result_abnormal_user", sa.Text(), comment="分析结果-异常用户数据方面"),
        sa.Column("result_monitor_blind", sa.Text(), comment="分析结果-监控补盲方面"),
        sa.Column("created_at", sa.DateTime(), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), comment="更新时间"),
        sa.ForeignKeyConstraint(["issue_id"], ["pmwb_operation_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issue_id"),
        sa.Index("idx_analysis_issue", "issue_id"),
        comment="主动运营分析工单明细表",
    )


def downgrade():
    op.drop_table("pmwb_operation_analysis")
