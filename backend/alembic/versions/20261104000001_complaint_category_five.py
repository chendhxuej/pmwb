"""客诉一级分类 4→5 类改造（系统问题/流程优化/数据异常/规则咨询/操作咨询）

背景：一级分类原为 4 类（系统问题/流程优化/投诉咨询/数据问题），其中
「投诉咨询」混装了两种性质完全不同的问题——客户不懂规则（规则咨询，靠解释即可化解）
与客户不会操作（操作咨询，靠指引/代操作化解）。两者压降手段不同，混在一起无法归因。

改造内容：
  1. 数据问题 → 数据异常（改名，口径不变）
  2. 投诉咨询拆为 规则咨询 / 操作咨询，按二级场景直接指定归属（不重跑 LLM）
  3. 工单表 category_l1 同步回填

Revision ID: 20261104000001
Revises: 20261103000003
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104000001"
down_revision = "20261103000003"
branch_labels = None
depends_on = None

# 二级场景 → 新一级的确定归属（拆自旧「投诉咨询」）
CONSULT_RULE = ("资费政策咨询", "退费与账单争议")          # 规则咨询：问政策/收费依据
CONSULT_OPER = ("操作指引", "查询与核实请求")              # 操作咨询：不会操作/要人查

# 一级排序（老大指定顺序）
L1 = (
    ("系统问题", 10),
    ("流程优化", 20),
    ("数据异常", 30),
    ("规则咨询", 40),
    ("操作咨询", 50),
)


def upgrade() -> None:
    conn = op.get_bind()

    # 1. 数据问题 → 数据异常（改名，先建新再改二级再删旧，避开 uk(level,name)）
    conn.execute(sa.text(
        "UPDATE pmwb_complaint_category SET name = '数据异常', sort_order = 30, "
        "note = '数据不一致/错误/缺失，需批量修复' WHERE level = 1 AND name = '数据问题'"))
    conn.execute(sa.text(
        "UPDATE pmwb_complaint_category SET parent_name = '数据异常' "
        "WHERE level = 2 AND parent_name = '数据问题'"))
    conn.execute(sa.text(
        "UPDATE pmwb_complaint_ticket SET category_l1 = '数据异常' WHERE category_l1 = '数据问题'"))

    # 2. 新建一级：规则咨询 / 操作咨询
    for name, order in L1:
        exists = conn.execute(sa.text(
            "SELECT id FROM pmwb_complaint_category WHERE level = 1 AND name = :n"
        ), {"n": name}).fetchone()
        if exists:
            conn.execute(sa.text(
                "UPDATE pmwb_complaint_category SET sort_order = :o WHERE level = 1 AND name = :n"
            ), {"o": order, "n": name})
        else:
            conn.execute(sa.text(
                "INSERT INTO pmwb_complaint_category (level, parent_name, name, keywords, "
                "sort_order, enabled, note, created_at, updated_at) "
                "VALUES (1, NULL, :n, NULL, :o, 1, :note, NOW(), NOW())"
            ), {"n": name, "o": order, "note": _l1_note(name)})

    # 3. 旧「投诉咨询」的二级按性质拆到新一级
    for names, target in ((CONSULT_RULE, "规则咨询"), (CONSULT_OPER, "操作咨询")):
        marks = ", ".join(f":n{i}" for i in range(len(names)))
        conn.execute(sa.text(
            f"UPDATE pmwb_complaint_category SET parent_name = :t "
            f"WHERE level = 2 AND name IN ({marks})"
        ), {"t": target, **{f"n{i}": v for i, v in enumerate(names)}})
        conn.execute(sa.text(
            f"UPDATE pmwb_complaint_ticket SET category_l1 = :t "
            f"WHERE category_l2 IN ({marks})"
        ), {"t": target, **{f"n{i}": v for i, v in enumerate(names)}})

    # 4. 删除旧一级「投诉咨询」（其二级已全部迁走；残留的兜底挂操作咨询）
    remain = conn.execute(sa.text(
        "SELECT COUNT(*) FROM pmwb_complaint_category WHERE level = 2 AND parent_name = '投诉咨询'"
    )).scalar()
    if remain:
        conn.execute(sa.text(
            "UPDATE pmwb_complaint_category SET parent_name = '操作咨询' "
            "WHERE level = 2 AND parent_name = '投诉咨询'"))
    conn.execute(sa.text(
        "UPDATE pmwb_complaint_ticket SET category_l1 = '操作咨询' WHERE category_l1 = '投诉咨询'"))
    old = conn.execute(sa.text(
        "SELECT id FROM pmwb_complaint_category WHERE level = 1 AND name = '投诉咨询'"
    )).fetchone()
    if old:
        conn.execute(sa.text("DELETE FROM pmwb_complaint_category WHERE id = :i"), {"i": old[0]})


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "INSERT INTO pmwb_complaint_category (level, parent_name, name, keywords, sort_order, "
        "enabled, note, created_at, updated_at) VALUES (1, NULL, '投诉咨询', NULL, 30, 1, "
        "'咨询解释类可引导化解', NOW(), NOW())"))
    conn.execute(sa.text(
        "UPDATE pmwb_complaint_category SET parent_name = '投诉咨询' "
        "WHERE level = 2 AND parent_name IN ('规则咨询', '操作咨询')"))
    conn.execute(sa.text(
        "UPDATE pmwb_complaint_ticket SET category_l1 = '投诉咨询' "
        "WHERE category_l1 IN ('规则咨询', '操作咨询')"))
    conn.execute(sa.text(
        "DELETE FROM pmwb_complaint_category WHERE level = 1 AND name IN ('规则咨询', '操作咨询')"))
    conn.execute(sa.text(
        "UPDATE pmwb_complaint_category SET name = '数据问题' WHERE level = 1 AND name = '数据异常'"))
    conn.execute(sa.text(
        "UPDATE pmwb_complaint_category SET parent_name = '数据问题' "
        "WHERE level = 2 AND parent_name = '数据异常'"))
    conn.execute(sa.text(
        "UPDATE pmwb_complaint_ticket SET category_l1 = '数据问题' WHERE category_l1 = '数据异常'"))


def _l1_note(name: str) -> str:
    return {
        "系统问题": "系统缺陷需研发修复",
        "流程优化": "流程或规则不合理需改造",
        "数据异常": "数据不一致/错误/缺失，需批量修复",
        "规则咨询": "客户对政策/资费/账务规则有疑问，解释说明即可化解",
        "操作咨询": "客户不熟悉操作或要求查询核实，指引/代办即可化解",
    }.get(name, "")
