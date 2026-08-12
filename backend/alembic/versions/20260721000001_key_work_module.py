"""重点工作模块：pmwb_key_work 主表 + 8 个子表。

三类（总部试点/年度任务/专题工作）共用一张主表，由 category 区分。
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260721000001"
down_revision: str = "20260720000001"
branch_labels: tuple = None
depends_on: tuple = None


def upgrade() -> None:
    op.create_table(
        "pmwb_key_work",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("work_no", sa.String(64), nullable=False, comment="重点工作编号 KW-YYYYMMDD-XXX"),
        sa.Column(
            "category",
            sa.Enum("hq_pilot", "annual_task", "special_topic", name="kw_category"),
            nullable=False,
            server_default="annual_task",
            comment="分类：总部试点/年度任务/专题工作",
        ),
        sa.Column("title", sa.String(500), nullable=False, comment="工作标题"),
        sa.Column("background", sa.Text(), nullable=True, comment="工作背景"),
        sa.Column("current_status", sa.Text(), nullable=True, comment="现状说明"),
        sa.Column("content", sa.Text(), nullable=True, comment="工作内容"),
        sa.Column("owner", sa.String(128), nullable=True, comment="牵头人/负责人"),
        sa.Column(
            "priority",
            sa.Enum("P0", "P1", "P2", "P3", name="kw_priority"),
            server_default="P2",
            comment="优先级",
        ),
        sa.Column(
            "status",
            sa.Enum("planning", "in_progress", "completed", "paused", "cancelled", name="kw_status"),
            server_default="planning",
            comment="生命周期状态",
        ),
        sa.Column("planned_finish_date", sa.Date(), nullable=True, comment="计划完成时间"),
        sa.Column("acceptance_criteria", sa.Text(), nullable=True, comment="验收标准(JSON数组)"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_no"),
        sa.Index("idx_kw_category", "category"),
        sa.Index("idx_kw_status", "status"),
        sa.Index("idx_kw_owner", "owner"),
        comment="重点工作主表",
    )

    op.create_table(
        "pmwb_key_work_goal",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("key_work_id", sa.Integer(), nullable=False, comment="关联重点工作ID"),
        sa.Column("seq", sa.Integer(), server_default="1", comment="指标序号"),
        sa.Column("indicator", sa.String(255), nullable=True, comment="指标名称"),
        sa.Column("target_value", sa.String(255), nullable=True, comment="目标值"),
        sa.Column("current_value", sa.String(255), nullable=True, comment="当前值"),
        sa.Column("unit", sa.String(32), nullable=True, comment="单位"),
        sa.Column("description", sa.Text(), nullable=True, comment="说明"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["key_work_id"], ["pmwb_key_work.id"]),
        sa.Index("idx_kwg_kw_id", "key_work_id"),
        comment="重点工作目标指标表",
    )

    op.create_table(
        "pmwb_key_work_milestone",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("key_work_id", sa.Integer(), nullable=False, comment="关联重点工作ID"),
        sa.Column("seq", sa.Integer(), server_default="1", comment="序号"),
        sa.Column("name", sa.String(255), nullable=False, comment="里程碑名称"),
        sa.Column("due_date", sa.Date(), nullable=True, comment="计划完成日期"),
        sa.Column(
            "status",
            sa.Enum("pending", "in_progress", "done", "delayed", name="kw_milestone_status"),
            server_default="pending",
            comment="状态",
        ),
        sa.Column("note", sa.Text(), nullable=True, comment="说明"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["key_work_id"], ["pmwb_key_work.id"]),
        sa.Index("idx_kwm_kw_id", "key_work_id"),
        comment="重点工作里程碑表",
    )

    op.create_table(
        "pmwb_key_work_member",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("key_work_id", sa.Integer(), nullable=False, comment="关联重点工作ID"),
        sa.Column("name", sa.String(64), nullable=False, comment="成员姓名"),
        sa.Column("role", sa.String(128), nullable=True, comment="角色"),
        sa.Column("division_desc", sa.Text(), nullable=True, comment="分工说明"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["key_work_id"], ["pmwb_key_work.id"]),
        sa.Index("idx_kwmbr_kw_id", "key_work_id"),
        comment="重点工作团队成员及分工表",
    )

    op.create_table(
        "pmwb_key_work_monthly_plan",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("key_work_id", sa.Integer(), nullable=False, comment="关联重点工作ID"),
        sa.Column("month", sa.String(7), nullable=False, comment="月份 YYYY-MM"),
        sa.Column("content", sa.Text(), nullable=True, comment="计划内容"),
        sa.Column(
            "status",
            sa.Enum("pending", "done", name="kw_plan_status"),
            server_default="pending",
            comment="状态",
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["key_work_id"], ["pmwb_key_work.id"]),
        sa.Index("idx_kwmp_kw_id", "key_work_id"),
        sa.Index("idx_kwmp_month", "month"),
        comment="重点工作月度计划表",
    )

    op.create_table(
        "pmwb_key_work_weekly_plan",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("key_work_id", sa.Integer(), nullable=False, comment="关联重点工作ID"),
        sa.Column("week", sa.String(10), nullable=False, comment="周次 YYYY-Www"),
        sa.Column("content", sa.Text(), nullable=True, comment="计划内容"),
        sa.Column(
            "status",
            sa.Enum("pending", "done", name="kw_plan_status"),
            server_default="pending",
            comment="状态",
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["key_work_id"], ["pmwb_key_work.id"]),
        sa.Index("idx_kwwp_kw_id", "key_work_id"),
        sa.Index("idx_kwwp_week", "week"),
        comment="重点工作周计划表",
    )

    op.create_table(
        "pmwb_key_work_progress",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("key_work_id", sa.Integer(), nullable=False, comment="关联重点工作ID"),
        sa.Column("record_date", sa.Date(), nullable=True, comment="进展日期"),
        sa.Column("reporter", sa.String(64), nullable=True, comment="汇报人"),
        sa.Column("content", sa.Text(), nullable=True, comment="进展内容"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["key_work_id"], ["pmwb_key_work.id"]),
        sa.Index("idx_kwp_kw_id", "key_work_id"),
        comment="重点工作进展日志表",
    )

    op.create_table(
        "pmwb_key_work_member_task",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("key_work_id", sa.Integer(), nullable=False, comment="关联重点工作ID"),
        sa.Column("title", sa.String(500), nullable=False, comment="待办标题"),
        sa.Column("assignee", sa.String(64), nullable=True, comment="负责人(成员姓名)"),
        sa.Column("due_date", sa.Date(), nullable=True, comment="截止日期"),
        sa.Column(
            "status",
            sa.Enum("todo", "in_progress", "done", "cancelled", name="kw_task_status"),
            server_default="todo",
            comment="状态",
        ),
        sa.Column(
            "link_type",
            sa.Enum("none", "milestone", "monthly_plan", "weekly_plan", name="kw_task_link"),
            server_default="none",
            comment="关联对象类型",
        ),
        sa.Column("link_id", sa.Integer(), nullable=True, comment="关联对象ID"),
        sa.Column("note", sa.Text(), nullable=True, comment="备注"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["key_work_id"], ["pmwb_key_work.id"]),
        sa.Index("idx_kwt_kw_id", "key_work_id"),
        sa.Index("idx_kwt_assignee", "assignee"),
        sa.Index("idx_kwt_due", "due_date"),
        comment="重点工作成员待办表",
    )

    op.create_table(
        "pmwb_key_work_deliverable",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="自增ID"),
        sa.Column("key_work_id", sa.Integer(), nullable=False, comment="关联重点工作ID"),
        sa.Column(
            "deliverable_type",
            sa.Enum("doc", "report", "data", "code", "other", name="kw_deliverable_type"),
            server_default="other",
            comment="交付物类型",
        ),
        sa.Column("file_name", sa.String(255), nullable=False, comment="文件名"),
        sa.Column("original_name", sa.String(255), nullable=True, comment="原始文件名"),
        sa.Column("file_size", sa.Integer(), nullable=True, comment="文件大小(字节)"),
        sa.Column("file_type", sa.String(64), nullable=True, comment="文件类型"),
        sa.Column("obsidian_path", sa.String(512), nullable=True, comment="Obsidian归档完整路径"),
        sa.Column("local_path", sa.String(512), nullable=True, comment="本地路径"),
        sa.Column("source", sa.String(32), server_default="upload", comment="来源"),
        sa.Column("source_url", sa.String(1024), nullable=True, comment="来源URL"),
        sa.Column("note", sa.Text(), nullable=True, comment="备注"),
        sa.Column("uploaded_by", sa.String(64), nullable=True, comment="上传人"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["key_work_id"], ["pmwb_key_work.id"]),
        sa.Index("idx_kwd_kw_id", "key_work_id"),
        comment="重点工作交付物表",
    )


def downgrade() -> None:
    op.drop_table("pmwb_key_work_deliverable")
    op.drop_table("pmwb_key_work_member_task")
    op.drop_table("pmwb_key_work_progress")
    op.drop_table("pmwb_key_work_weekly_plan")
    op.drop_table("pmwb_key_work_monthly_plan")
    op.drop_table("pmwb_key_work_member")
    op.drop_table("pmwb_key_work_milestone")
    op.drop_table("pmwb_key_work_goal")
    op.drop_table("pmwb_key_work")
    sa.Enum(name="kw_category").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="kw_priority").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="kw_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="kw_milestone_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="kw_plan_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="kw_task_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="kw_task_link").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="kw_deliverable_type").drop(op.get_bind(), checkfirst=True)
