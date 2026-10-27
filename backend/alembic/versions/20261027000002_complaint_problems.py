"""客诉共性问题闭环管理：问题台账表 + 问题↔措施关联表 + 工单归因列

- pmwb_complaint_problem      共性问题台账（唯一归因键 problem_no）
- pmwb_complaint_problem_action 问题↔措施 多对多关联
- pmwb_complaint_ticket       增列 problem_no + idx_ct_problem

无种子数据（问题为运行时生成，不造假台账）；历史不回溯（从首运周起）。
多 head 仓库：须显式 `alembic upgrade 20261027000002`。
revision: 20261027000002 / down_revision: 20261027000001
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20261027000002"
down_revision = "20261027000001"
branch_labels = None
depends_on = None

PROBLEM = "pmwb_complaint_problem"
LINK = "pmwb_complaint_problem_action"
TICKET = "pmwb_complaint_ticket"


def _has_table(bind, name: str) -> bool:
    return inspect(bind).has_table(name)


def _has_index(bind, table: str, index: str) -> bool:
    try:
        return any(ix["name"] == index for ix in inspect(bind).get_indexes(table))
    except Exception:
        return False


def _has_column(bind, table: str, column: str) -> bool:
    try:
        return any(c["name"] == column for c in inspect(bind).get_columns(table))
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. 共性问题台账 ──
    if not _has_table(bind, PROBLEM):
        op.create_table(
            PROBLEM,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, comment="自增ID"),
            sa.Column("problem_no", sa.String(64), nullable=False, unique=True,
                      comment="问题编号（CPB-2026W44-01）"),
            sa.Column("title", sa.String(255), nullable=False, comment="问题标题（规则自动生成，可人工改）"),
            sa.Column("category_l1", sa.String(64), comment="一级问题性质（快照）"),
            sa.Column("category_l2", sa.String(64), nullable=False, comment="二级问题场景（归并锚点）"),
            sa.Column("source_type", sa.String(32), nullable=False, server_default="candidate",
                      comment="主触发规则：batch_cluster/top_scene/surge/recur/manual"),
            sa.Column("rule_hits", sa.String(128), comment="全部命中规则（逗号分隔，证据不参与分支）"),
            sa.Column("evidence", sa.Text(), comment="证据快照 JSON（只读）"),
            sa.Column("status", sa.String(32), nullable=False, server_default="candidate",
                      comment="状态：candidate/open/resolving/closed/ignored/merged"),
            sa.Column("first_week", sa.String(16), nullable=False, comment="首见周（ISO）"),
            sa.Column("last_week", sa.String(16), comment="末见周（每周导入回写）"),
            sa.Column("active_weeks", sa.Integer(), nullable=False, server_default="0",
                      comment="连续在办周数"),
            sa.Column("quiet_weeks", sa.Integer(), nullable=False, server_default="0",
                      comment="连续零复发周数（闭环建议用）"),
            sa.Column("week_cnt", sa.Integer(), nullable=False, server_default="0",
                      comment="最近一周该场景单量"),
            sa.Column("peak_cnt", sa.Integer(), nullable=False, server_default="0",
                      comment="生命周期单周峰值"),
            sa.Column("total_cnt", sa.Integer(), nullable=False, server_default="0",
                      comment="生命周期累计单量（按周累加）"),
            sa.Column("recur_cnt", sa.Integer(), nullable=False, server_default="0",
                      comment="累计复发单量（is_recur 口径）"),
            sa.Column("recur_weeks", sa.Integer(), nullable=False, server_default="0",
                      comment="连续复发周数"),
            sa.Column("reopen_flag", sa.Integer(), nullable=False, server_default="0",
                      comment="1=已闭环问题再次出现（建议重开）"),
            sa.Column("owner", sa.String(255), comment="问题责任人（多负责人逗号分隔）"),
            sa.Column("confirm_by", sa.String(64), comment="候选确认人"),
            sa.Column("confirm_at", sa.DateTime(), comment="候选确认时间"),
            sa.Column("conclusion", sa.String(500), comment="闭环结论（closed 必填）"),
            sa.Column("closed_week", sa.String(16), comment="闭环周"),
            sa.Column("closed_at", sa.DateTime(), comment="闭环时间"),
            sa.Column("merged_into", sa.String(64), comment="合并目标 problem_no（仅 merged 有值）"),
            sa.Column("note", sa.Text(), comment="备注"),
            sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), nullable=False, comment="更新时间"),
            comment="客诉共性问题台账（闭环管理主体）",
        )
    for ix, cols in (
        ("idx_cp_status", ["status"]),
        ("idx_cp_l2", ["category_l2"]),
        ("idx_cp_week", ["last_week"]),
        ("idx_cp_source", ["source_type"]),
    ):
        if not _has_index(bind, PROBLEM, ix):
            op.create_index(ix, PROBLEM, cols)

    # ── 2. 问题↔措施 多对多 ──
    if not _has_table(bind, LINK):
        op.create_table(
            LINK,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, comment="自增ID"),
            sa.Column("problem_no", sa.String(64), nullable=False, comment="问题编号"),
            sa.Column("action_no", sa.String(64), nullable=False, comment="措施编号"),
            sa.Column("is_primary", sa.Integer(), nullable=False, server_default="0",
                      comment="主措施标记：1 是 0 否"),
            sa.Column("linked_by", sa.String(64), comment="关联操作人"),
            sa.Column("linked_at", sa.DateTime(), nullable=False, comment="关联时间"),
            sa.Column("note", sa.String(255), comment="关联说明"),
            sa.UniqueConstraint("problem_no", "action_no", name="uk_cpp_linked"),
            comment="共性问题↔改进措施多对多关联",
        )
    if not _has_index(bind, LINK, "idx_cpp_action"):
        op.create_index("idx_cpp_action", LINK, ["action_no"])

    # ── 3. 工单归因列 ──
    if not _has_column(bind, TICKET, "problem_no"):
        op.add_column(TICKET, sa.Column("problem_no", sa.String(64),
                                        comment="归属共性问题编号（唯一归因键）"))
    if not _has_index(bind, TICKET, "idx_ct_problem"):
        op.create_index("idx_ct_problem", TICKET, ["problem_no"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has_index(bind, TICKET, "idx_ct_problem"):
        op.drop_index("idx_ct_problem", table_name=TICKET)
    if _has_column(bind, TICKET, "problem_no"):
        op.drop_column(TICKET, "problem_no")
    for tbl in (LINK, PROBLEM):
        if _has_table(bind, tbl):
            op.drop_table(tbl)
