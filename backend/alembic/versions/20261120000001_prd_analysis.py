"""PRD 需求分析：主表 / 引用来源 / 冲突清单

- pmwb_prd_analysis：一次分析一条，旁挂 req_id，不改写现有需求/用户故事模型。
- pmwb_prd_source：知识引用（系统ID+仓库ID+SHA+路径+条款）。
- pmwb_prd_conflict：CL 定级冲突清单。

⚠ 项目 alembic 存在多 head（坏壳 20260908105939），执行须显式指定：
  alembic upgrade 20261120000001

Revision ID: 20261120000001
Revises: 20261119000002
Create Date: 2026-11-20
"""
from alembic import op
import sqlalchemy as sa

revision = "20261120000001"
down_revision = "20261119000002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pmwb_prd_analysis",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trace_id", sa.String(64), nullable=False),
        sa.Column("req_id", sa.String(64), nullable=False),
        sa.Column("req_name", sa.String(500)),
        sa.Column("mode", sa.String(16), nullable=False, server_default="qa"),
        sa.Column("profile", sa.String(16), nullable=False, server_default="concise"),
        sa.Column("systems", sa.Text()),
        sa.Column("answers", sa.Text()),
        sa.Column("prd_markdown", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="generated"),
        sa.Column("gen_strategy", sa.String(32)),
        sa.Column("gen_provider", sa.String(128)),
        sa.Column("gen_model", sa.String(128)),
        sa.Column("gen_fallback_reason", sa.Text()),
        sa.Column("knowledge_mode", sa.String(16), nullable=False, server_default="none"),
        sa.Column("knowledge_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notice", sa.Text()),
        sa.Column("prd_file_path", sa.String(500)),
        sa.Column("finalized", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("finalized_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.UniqueConstraint("trace_id", name="uq_prd_analysis_trace"),
    )
    op.create_index("idx_prd_analysis_req", "pmwb_prd_analysis", ["req_id"])
    op.create_index("idx_prd_analysis_trace", "pmwb_prd_analysis", ["trace_id"])

    op.create_table(
        "pmwb_prd_source",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trace_id", sa.String(64), nullable=False),
        sa.Column("sys_id", sa.String(64)),
        sa.Column("repo_id", sa.String(128)),
        sa.Column("sha", sa.String(64)),
        sa.Column("path", sa.String(500)),
        sa.Column("clause", sa.String(255)),
        sa.Column("quote", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_index("idx_prd_source_trace", "pmwb_prd_source", ["trace_id"])

    op.create_table(
        "pmwb_prd_conflict",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trace_id", sa.String(64), nullable=False),
        sa.Column("level", sa.String(16)),
        sa.Column("type", sa.String(64)),
        sa.Column("desc", sa.Text()),
        sa.Column("evidence", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_index("idx_prd_conflict_trace", "pmwb_prd_conflict", ["trace_id"])


def downgrade():
    op.drop_index("idx_prd_conflict_trace", table_name="pmwb_prd_conflict")
    op.drop_table("pmwb_prd_conflict")
    op.drop_index("idx_prd_source_trace", table_name="pmwb_prd_source")
    op.drop_table("pmwb_prd_source")
    op.drop_index("idx_prd_analysis_trace", table_name="pmwb_prd_analysis")
    op.drop_index("idx_prd_analysis_req", table_name="pmwb_prd_analysis")
    op.drop_table("pmwb_prd_analysis")
