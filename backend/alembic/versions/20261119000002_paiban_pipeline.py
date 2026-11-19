"""排版管理 pb-2 ~ pb-8：跟踪主行 / 团队子行 / 参与记录 / 留痕 / 风险 / 督办 / 反馈

- pmwb_pb_track：工单维度全局唯一主行，版本统计唯一分母；终态仅 live / cancelled。
- pmwb_pb_track_team：工单 × 团队，团队视图唯一分母（与主行口径不可加总）。
- pmwb_pb_participation：主行 × 版本参与记录，按计划上线率唯一分母来源。
- pmwb_pb_stage_log / _risk / _supervise_batch / _supervise_item / _feedback：
  留痕、硬门禁风险、督办回执、四通道反馈闭环。

⚠ 项目 alembic 存在多 head（坏壳 20260908105939），执行须显式指定：
  alembic upgrade 20261119000002

Revision ID: 20261119000002
Revises: 20261119000001
Create Date: 2026-11-19
"""
from alembic import op
import sqlalchemy as sa

revision = "20261119000002"
down_revision = "20261119000001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pmwb_pb_track",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticket_type", sa.String(8), nullable=False),
        sa.Column("ticket_no", sa.String(128), nullable=False),
        sa.Column("title", sa.String(500)),
        sa.Column("system_name", sa.String(128)),
        sa.Column("priority", sa.String(16)),
        sa.Column("owner", sa.String(512)),
        sa.Column("expected_date", sa.Date()),
        sa.Column("current_plan_id", sa.Integer()),
        sa.Column("plan_source", sa.String(16)),
        sa.Column("stage", sa.String(16), nullable=False),
        sa.Column("stage_entered_at", sa.DateTime()),
        sa.Column("wait_release_at", sa.DateTime()),
        sa.Column("admit_status", sa.String(16), nullable=False),
        sa.Column("admit_decided_at", sa.DateTime()),
        sa.Column("exception_flag", sa.Integer(), nullable=False),
        sa.Column("exception_reason", sa.String(64)),
        sa.Column("exception_operator", sa.String(64)),
        sa.Column("exception_at", sa.DateTime()),
        sa.Column("exception_fact", sa.Text()),
        sa.Column("before_value", sa.Text()),
        sa.Column("result", sa.String(16), nullable=False),
        sa.Column("result_date", sa.Date()),
        sa.Column("result_reason", sa.String(500)),
        sa.Column("result_operator", sa.String(64)),
        sa.Column("result_at", sa.DateTime()),
        sa.Column("defer_count", sa.Integer(), nullable=False),
        sa.Column("fail_count", sa.Integer(), nullable=False),
        sa.Column("plan_chain", sa.Text()),
        sa.Column("last_defer_reason", sa.String(128)),
        sa.Column("last_defer_at", sa.DateTime()),
        sa.Column("focus_flag", sa.Integer(), nullable=False),
        sa.Column("abnormal_flag", sa.Integer(), nullable=False),
        sa.Column("freeze_late", sa.Integer(), nullable=False),
        sa.Column("source_conflict", sa.Integer(), nullable=False),
        sa.Column("source_snapshot", sa.Text()),
        sa.Column("source_snapshot_sig", sa.String(255)),
        sa.Column("include_source", sa.String(16)),
        sa.Column("included_at", sa.DateTime()),
        sa.Column("included_by", sa.String(64)),
        sa.Column("active", sa.Integer(), nullable=False),
        sa.Column("removed_at", sa.DateTime()),
        sa.Column("removed_reason", sa.String(255)),
        sa.Column("supervise_count", sa.Integer(), nullable=False),
        sa.Column("last_supervise_at", sa.DateTime()),
        sa.Column("pending_receipt_batch", sa.String(64)),
        sa.Column("feedback_count", sa.Integer(), nullable=False),
        sa.Column("last_feedback_at", sa.DateTime()),
        sa.Column("pending_feedback", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.UniqueConstraint("ticket_type", "ticket_no", name="uq_pb_track_anchor"),
    )
    op.create_index("idx_pb_track_plan", "pmwb_pb_track", ["current_plan_id"])
    op.create_index("idx_pb_track_active", "pmwb_pb_track", ["active"])

    op.create_table(
        "pmwb_pb_track_team",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("team_name", sa.String(128), nullable=False),
        sa.Column("owner", sa.String(512)),
        sa.Column("stage", sa.String(16), nullable=False),
        sa.Column("stage_entered_at", sa.DateTime()),
        sa.Column("done", sa.Integer(), nullable=False),
        sa.Column("parse_status", sa.String(16)),
        sa.Column("recipient_status", sa.String(16)),
        sa.Column("note", sa.String(500)),
        sa.Column("last_feedback_at", sa.DateTime()),
        sa.Column("supervise_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.UniqueConstraint("track_id", "team_name", name="uq_pb_team_anchor"),
    )
    op.create_index("idx_pb_team_track", "pmwb_pb_track_team", ["track_id"])
    op.create_index("idx_pb_team_name", "pmwb_pb_track_team", ["team_name"])

    op.create_table(
        "pmwb_pb_participation",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.String(64)),
        sa.Column("joined_at", sa.DateTime()),
        sa.Column("left_at", sa.DateTime()),
        sa.Column("admit_status", sa.String(16)),
        sa.Column("result", sa.String(16)),
        sa.Column("result_date", sa.Date()),
        sa.Column("is_exception", sa.Integer(), nullable=False),
        sa.Column("freeze_late", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(16)),
        sa.UniqueConstraint("track_id", "plan_id", name="uq_pb_participation"),
    )
    op.create_index("idx_pb_part_plan", "pmwb_pb_participation", ["plan_id"])

    op.create_table(
        "pmwb_pb_stage_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer()),
        sa.Column("from_stage", sa.String(16)),
        sa.Column("to_stage", sa.String(16), nullable=False),
        sa.Column("is_rollback", sa.Integer(), nullable=False),
        sa.Column("rollback_count", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(500)),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("operator", sa.String(64)),
        sa.Column("feedback_id", sa.Integer()),
        sa.Column("risk_id", sa.Integer()),
        sa.Column("batch_no", sa.String(64)),
        sa.Column("before_value", sa.Text()),
        sa.Column("after_value", sa.Text()),
        sa.Column("new_deadline", sa.String(16)),
        sa.Column("changed_at", sa.DateTime()),
    )
    op.create_index("idx_pb_stagelog_track", "pmwb_pb_stage_log", ["track_id"])

    op.create_table(
        "pmwb_pb_risk",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer()),
        sa.Column("risk_type", sa.String(32), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("affect_release", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(8)),
        sa.Column("source", sa.String(24)),
        sa.Column("raw_ref", sa.Text()),
        sa.Column("reporter", sa.String(64)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("merge_count", sa.Integer(), nullable=False),
        sa.Column("resolution", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("resolved_at", sa.DateTime()),
    )
    op.create_index("idx_pb_risk_track", "pmwb_pb_risk", ["track_id"])
    op.create_index("idx_pb_risk_blocking", "pmwb_pb_risk",
                    ["track_id", "affect_release", "status"])

    op.create_table(
        "pmwb_pb_supervise_batch",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("batch_no", sa.String(64), nullable=False, unique=True),
        sa.Column("team_name", sa.String(128), nullable=False),
        sa.Column("ticket_type", sa.String(8), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("rules_snapshot", sa.Text()),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("sent_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("mail_result", sa.Text()),
        sa.Column("dry_run", sa.Integer(), nullable=False),
        sa.Column("confirm_send", sa.Integer(), nullable=False),
        sa.Column("ignore_cooldown", sa.Integer(), nullable=False),
        sa.Column("exception_reason", sa.String(128)),
        sa.Column("operator", sa.String(64)),
        sa.Column("receipt_deadline", sa.String(16)),
        sa.Column("receipt_status", sa.String(16)),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_index("idx_pb_batch_plan", "pmwb_pb_supervise_batch", ["plan_id"])

    op.create_table(
        "pmwb_pb_supervise_item",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("batch_no", sa.String(64)),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer()),
        sa.Column("ticket_no", sa.String(128)),
        sa.Column("receipt_code", sa.String(128), nullable=False, unique=True),
        sa.Column("send_status", sa.String(16), nullable=False),
        sa.Column("skip_reason", sa.String(128)),
        sa.Column("failure_reason", sa.String(255)),
        sa.Column("supervise_seq", sa.Integer(), nullable=False),
        sa.Column("cooldown_left_h", sa.Integer(), nullable=False),
        sa.Column("triggered_rules", sa.Text()),
        sa.Column("receipt_status", sa.String(16)),
        sa.Column("receipt_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("batch_id", "track_id", "team_id", name="uq_pb_supervise_item"),
    )
    op.create_index("idx_pb_supitem_batch", "pmwb_pb_supervise_item", ["batch_id"])

    op.create_table(
        "pmwb_pb_feedback",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer()),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("batch_no", sa.String(64)),
        sa.Column("receipt_code", sa.String(128)),
        sa.Column("message_id", sa.String(255)),
        sa.Column("source_ref", sa.String(255)),
        sa.Column("sender", sa.String(128)),
        sa.Column("raw_text", sa.Text()),
        sa.Column("parsed_json", sa.Text()),
        sa.Column("suggested_json", sa.Text()),
        sa.Column("adopt_status", sa.String(16), nullable=False),
        sa.Column("before_value", sa.Text()),
        sa.Column("after_value", sa.Text()),
        sa.Column("stage_log_id", sa.Integer()),
        sa.Column("risk_id", sa.Integer()),
        sa.Column("reviewer", sa.String(64)),
        sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("review_note", sa.String(500)),
        sa.Column("rolled_back", sa.Integer(), nullable=False),
        sa.Column("rollback_at", sa.DateTime()),
        sa.Column("pending_rerun", sa.Integer(), nullable=False),
        sa.Column("reporter", sa.String(64)),
        sa.Column("feedback_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("message_id", "track_id", name="uq_pb_feedback_mail"),
    )
    op.create_index("idx_pb_feedback_track", "pmwb_pb_feedback", ["track_id"])
    op.create_index("idx_pb_feedback_status", "pmwb_pb_feedback", ["adopt_status"])


def downgrade():
    for t in (
        "pmwb_pb_feedback", "pmwb_pb_supervise_item", "pmwb_pb_supervise_batch",
        "pmwb_pb_risk", "pmwb_pb_stage_log", "pmwb_pb_participation",
        "pmwb_pb_track_team", "pmwb_pb_track",
    ):
        op.drop_table(t)
