"""complaint ticket AI 归类字段：ai_confidence / ai_evidence

LLM 主导分析引擎（方案 v3.0）输出落库：
  - ai_confidence：置信度 0~1，>= 阈值自动归类，< 阈值进人工确认队列；
  - ai_evidence：LLM 判断依据摘录（可追溯）。

幂等：_has_column 探测，列已存在跳过。
Revision ID: 20261030000002
Revises: 20261030000001
"""
from alembic import op
from sqlalchemy import text

revision = "20261030000002"
down_revision = "20261030000001"
branch_labels = None
depends_on = None


def _has_column(conn, table: str, col: str) -> bool:
    rows = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema=DATABASE() AND table_name=:t AND column_name=:c"
    ), {"t": table, "c": col}).scalar()
    return bool(rows)


def upgrade() -> None:
    conn = op.get_bind()
    if not _has_column(conn, "pmwb_complaint_ticket", "ai_confidence"):
        conn.execute(text(
            "ALTER TABLE pmwb_complaint_ticket "
            "ADD COLUMN ai_confidence FLOAT NULL COMMENT 'AI 归类置信度（0~1，LLM 主导分析输出）'"
        ))
    if not _has_column(conn, "pmwb_complaint_ticket", "ai_evidence"):
        conn.execute(text(
            "ALTER TABLE pmwb_complaint_ticket "
            "ADD COLUMN ai_evidence TEXT NULL COMMENT 'AI 判断依据摘录（LLM 分析输出，可追溯）'"
        ))


def downgrade() -> None:
    conn = op.get_bind()
    if _has_column(conn, "pmwb_complaint_ticket", "ai_evidence"):
        conn.execute(text("ALTER TABLE pmwb_complaint_ticket DROP COLUMN ai_evidence"))
    if _has_column(conn, "pmwb_complaint_ticket", "ai_confidence"):
        conn.execute(text("ALTER TABLE pmwb_complaint_ticket DROP COLUMN ai_confidence"))
