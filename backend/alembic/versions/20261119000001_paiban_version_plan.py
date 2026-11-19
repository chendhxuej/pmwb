"""排版管理 pb-1：版本计划 + 变更日志两表

- pmwb_pb_version_plan：默认统一计划 + 系统覆盖；发布日为唯一基准，
  四环节截止（−15/−8/−3/−1）与准入判定时点由常量**派生不落库**，改期自动重算。
- pmwb_pb_version_change_log：发布日 / 状态 / 准入规则变更逐字段留痕，
  affected_count 记录受影响的在跟主行数（pb-2 建表前恒 0）。
- 准入规则（CRM 提前 7 自然日 / 默认自动顺延）只配在版本计划上，禁工单级开关。

⚠ 项目 alembic 存在多 head（坏壳 20260908105939），执行须显式指定：
  alembic upgrade 20261119000001

Revision ID: 20261119000001
Revises: 20261110000001
Create Date: 2026-11-19
"""
from alembic import op
import sqlalchemy as sa

revision = "20261119000001"
down_revision = "20261110000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pmwb_pb_version_plan",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("version_no", sa.String(64), nullable=False, comment="版本标识，同范围内唯一"),
        sa.Column("scope_type", sa.String(16), nullable=False, server_default="system",
                  comment="default=统一默认 / system=指定系统"),
        sa.Column("system_name", sa.String(128), nullable=True, comment="指定系统名（default 时为空）"),
        sa.Column("system_verified", sa.Integer(), nullable=False, server_default="1",
                  comment="0=中台字典不可达，待自动补校验"),
        sa.Column("version_type", sa.String(16), nullable=False, server_default="regular",
                  comment="regular/emergency/ad_hoc"),
        sa.Column("release_date", sa.Date(), nullable=False, comment="计划发布日（倒排唯一基准）"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft",
                  comment="draft/confirmed/published/closed/cancelled"),
        sa.Column("admit_mode", sa.String(24), nullable=False, server_default="open",
                  comment="open / wait_release_n_days（CRM=提前 7 自然日）"),
        sa.Column("admit_lead_days", sa.Integer(), nullable=False, server_default="0",
                  comment="提前准入天数"),
        sa.Column("allow_temp_merge", sa.Integer(), nullable=False, server_default="1",
                  comment="0=未准入默认自动顺延；留本版须走单据级手工例外放行"),
        sa.Column("next_version_id", sa.Integer(), nullable=True, comment="人工指定顺延目标版本"),
        sa.Column("remark", sa.Text(), nullable=True, comment="窗口说明"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("scope_type", "system_name", "version_no", name="uq_pb_plan_scope_no"),
    )
    op.create_index("idx_pb_plan_release", "pmwb_pb_version_plan", ["release_date"])
    op.create_index("idx_pb_plan_scope", "pmwb_pb_version_plan", ["scope_type", "system_name"])

    op.create_table(
        "pmwb_pb_version_change_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.String(64), nullable=True, comment="变更时的版本标识快照"),
        sa.Column("change_type", sa.String(16), nullable=False, server_default="update",
                  comment="create / update"),
        sa.Column("field", sa.String(64), nullable=False, comment="变更字段"),
        sa.Column("old_value", sa.String(255), nullable=True),
        sa.Column("new_value", sa.String(255), nullable=True),
        sa.Column("affected_count", sa.Integer(), nullable=False, server_default="0",
                  comment="受影响的在跟主行数"),
        sa.Column("operator", sa.String(64), nullable=True),
        sa.Column("changed_at", sa.DateTime(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
    )
    op.create_index("idx_pb_log_plan", "pmwb_pb_version_change_log", ["plan_id"])


def downgrade() -> None:
    op.drop_index("idx_pb_log_plan", table_name="pmwb_pb_version_change_log")
    op.drop_table("pmwb_pb_version_change_log")
    op.drop_index("idx_pb_plan_scope", table_name="pmwb_pb_version_plan")
    op.drop_index("idx_pb_plan_release", table_name="pmwb_pb_version_plan")
    op.drop_table("pmwb_pb_version_plan")
