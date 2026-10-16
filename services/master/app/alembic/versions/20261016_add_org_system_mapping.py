"""add org system mapping columns (org_type / target_system_name / aliases)

把「内部组织 → 外部工单系统名称」的映射落到组织表本身，替代 PMWB 侧的独立字典
pmwb_vendor_team。

口径（全站统一，禁各处另写）：
  · org_type 取值域见 app/services/basic_data.py::ORG_TYPES（system/department/branch）
  · target_system_name 为空 = 映射到自身 name，即 COALESCE(NULLIF(target_system_name,''), name)
  · 多个组织填同一个 target_system_name 即「多对一」
  · aliases 半角逗号分隔，精确比对必须在 Python 侧做，禁 SQL LIKE 子串（会误命中）

本迁移**幂等**：列已存在则跳过；数据回填按 id / name 精确匹配，可重复执行。
downgrade 只删三列，「能运」组织行保留（它是真实存在的系统，删列不删组织）。

Revision ID: 20261016_add_org_system_mapping
Create Date: 2026-10-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision: str = "20261016_add_org_system_mapping"
down_revision: Union[str, Sequence[str], None] = "20260727_add_pmwb_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── 回填分组（依据 2026-10-16 数据摸底：pmwb_master.pmwb_org 20 行）──────────
SYSTEM_ORG_IDS = (32, 33, 34, 35, 36, 122, 123, 408)  # 8 个真实系统
BRANCH_ORG_IDS = (586, 587)                            # 地市分公司
DEPARTMENT_ORG_IDS = (37, 38, 39, 40, 42, 43, 84, 124, 125, 590)  # 部门 / 待确认的空壳

# 「能运」：评估表有 3 行但中台无此组织 → 新建为 system
MISSING_SYSTEM_ORG = "能运"
# 「电子协议系统」是「电子协议」的别名写法 → 给 id=122 写 aliases，不新建组织
ELECTRONIC_PROTOCOL_ORG_ID = 122
ELECTRONIC_PROTOCOL_ALIAS = "电子协议系统"


def _has_column(bind, table: str, column: str) -> bool:
    try:
        cols = [c["name"] for c in inspect(bind).get_columns(table)]
    except Exception:
        return False
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1) 加列（幂等）──────────────────────────────────────────────
    if not _has_column(bind, "pmwb_org", "org_type"):
        op.add_column(
            "pmwb_org",
            sa.Column(
                "org_type",
                sa.String(length=32),
                nullable=False,
                server_default="department",
                comment="组织类型：system/department/branch（禁 ENUM，合法值见 ORG_TYPES）",
            ),
        )
    if not _has_column(bind, "pmwb_org", "target_system_name"):
        op.add_column(
            "pmwb_org",
            sa.Column(
                "target_system_name",
                sa.String(length=128),
                nullable=True,
                comment="映射到的目标系统名；为空=映射到自身 name；多组织同值=多对一",
            ),
        )
    if not _has_column(bind, "pmwb_org", "aliases"):
        op.add_column(
            "pmwb_org",
            sa.Column(
                "aliases",
                sa.String(length=512),
                nullable=True,
                comment="工单标题中可能出现的别名，半角逗号分隔（精确比对在 Python 侧，禁 LIKE 子串）",
            ),
        )

    # ── 2) 索引（幂等：先探测 information_schema）─────────────────────
    for idx_name, col in (("idx_org_type", "org_type"), ("idx_org_target_system", "target_system_name")):
        exists = bind.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() AND table_name = 'pmwb_org' AND index_name = :n"
            ),
            {"n": idx_name},
        ).scalar()
        if not exists:
            op.create_index(idx_name, "pmwb_org", [col])

    # ── 3) org_type 回填（按 id 精确更新，可重复执行）─────────────────
    if SYSTEM_ORG_IDS:
        bind.execute(
            text("UPDATE pmwb_org SET org_type = 'system' WHERE id IN :ids").bindparams(
                sa.bindparam("ids", value=list(SYSTEM_ORG_IDS), expanding=True)
            )
        )
    if BRANCH_ORG_IDS:
        bind.execute(
            text("UPDATE pmwb_org SET org_type = 'branch' WHERE id IN :ids").bindparams(
                sa.bindparam("ids", value=list(BRANCH_ORG_IDS), expanding=True)
            )
        )
    if DEPARTMENT_ORG_IDS:
        bind.execute(
            text("UPDATE pmwb_org SET org_type = 'department' WHERE id IN :ids").bindparams(
                sa.bindparam("ids", value=list(DEPARTMENT_ORG_IDS), expanding=True)
            )
        )

    # ── 4) 补「能运」（按 name 判重，不硬编 id）───────────────────────
    exists_ny = bind.execute(
        text("SELECT COUNT(*) FROM pmwb_org WHERE name = :n"), {"n": MISSING_SYSTEM_ORG}
    ).scalar()
    if not exists_ny:
        bind.execute(
            text(
                "INSERT INTO pmwb_org (name, description, sort, enabled, source_trace, created_at, org_type) "
                "VALUES (:n, :d, 99, 1, 'manual', NOW(), 'system')"
            ),
            {"n": MISSING_SYSTEM_ORG, "d": "由系统别名映射迁移补建（评估表中存在但中台原无此组织）"},
        )

    # ── 5) 给「电子协议」写别名（不覆盖人工已填值）─────────────────────
    bind.execute(
        text(
            "UPDATE pmwb_org SET aliases = :a "
            "WHERE id = :id AND (aliases IS NULL OR aliases = '')"
        ),
        {"a": ELECTRONIC_PROTOCOL_ALIAS, "id": ELECTRONIC_PROTOCOL_ORG_ID},
    )


def downgrade() -> None:
    bind = op.get_bind()
    for idx_name in ("idx_org_target_system", "idx_org_type"):
        exists = bind.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() AND table_name = 'pmwb_org' AND index_name = :n"
            ),
            {"n": idx_name},
        ).scalar()
        if exists:
            op.drop_index(idx_name, table_name="pmwb_org")
    for col in ("aliases", "target_system_name", "org_type"):
        if _has_column(bind, "pmwb_org", col):
            op.drop_column("pmwb_org", col)
