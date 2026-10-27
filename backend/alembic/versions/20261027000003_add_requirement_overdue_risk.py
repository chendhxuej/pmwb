"""需求超期风险标记：pmwb_requirement_ext 增加三列

- overdue_risk      手工「超期风险」标记（0/1），用户在需求列表对开发中滞留需求人工打标
- overdue_risk_at   打标时间（now_cn）
- overdue_risk_note 打标备注（256 字，clear 时保留便于追溯）

联动：sensitive_req.sync 将 overdue_risk=1 的需求纳入敏感跟踪池（judge_reason=R5:dev_overdue，
等同级别命中待遇）；dismiss 永不复活语义不受影响。
存量数据默认 0，不影响既有逻辑。
多 head 仓库：须显式 `alembic upgrade 20261027000003`。
revision: 20261027000003 / down_revision: 20261027000002
"""

from alembic import op
import sqlalchemy as sa

revision = "20261027000003"
down_revision = "20261027000002"
branch_labels = None
depends_on = None

TABLE = "pmwb_requirement_ext"


def _existing_columns(conn) -> set:
    insp = sa.inspect(conn)
    return {c["name"] for c in insp.get_columns(TABLE)}


def upgrade() -> None:
    conn = op.get_bind()
    cols = _existing_columns(conn)

    if "overdue_risk" not in cols:
        op.add_column(
            TABLE,
            sa.Column(
                "overdue_risk",
                sa.Integer(),
                nullable=True,
                server_default="0",
                comment="手工超期风险标记(1是)，用户在需求列表人工打标，敏感跟踪池按此纳入(R5)",
            ),
        )
    if "overdue_risk_at" not in cols:
        op.add_column(
            TABLE,
            sa.Column(
                "overdue_risk_at",
                sa.DateTime(),
                comment="超期风险打标时间",
            ),
        )
    if "overdue_risk_note" not in cols:
        op.add_column(
            TABLE,
            sa.Column(
                "overdue_risk_note",
                sa.String(256),
                comment="超期风险打标备注（取消标记时保留便于追溯）",
            ),
        )

    # 存量补 0，保证判定查询不受 NULL 影响
    conn.execute(
        sa.text(f"UPDATE {TABLE} SET overdue_risk = 0 WHERE overdue_risk IS NULL")
    )


def downgrade() -> None:
    conn = op.get_bind()
    cols = _existing_columns(conn)
    if "overdue_risk_note" in cols:
        op.drop_column(TABLE, "overdue_risk_note")
    if "overdue_risk_at" in cols:
        op.drop_column(TABLE, "overdue_risk_at")
    if "overdue_risk" in cols:
        op.drop_column(TABLE, "overdue_risk")
