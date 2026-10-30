"""complaint category l1 v4: 7 类业务场景维度 → 4 类问题性质维度

一级大类重构（方案 v3.0，老大 2026-10-30 拍板方案A）：
  系统问题 / 流程优化 / 投诉咨询 / 数据问题

映射规则：
  1) category_l2 非空 → 按 L2_TO_L1 逐场景映射（权威）；
  2) category_l2 为空 → 按 L1_DEFAULT 按旧一级整体归入新一级（取该旧类下多数场景的性质）；
  3) 未分类 / 空串保持不变。

幂等：新一级「系统问题」已存在且旧一级「计费与出账争议」不存在时跳过。
Revision ID: 20261030000001
Revises: 20261027000002
"""
from alembic import op
from sqlalchemy import text

revision = "20261030000001"
down_revision = "20261027000002"
branch_labels = None
depends_on = None

NEW_L1 = [
    ("系统问题", 10, "Bug/接口报错/功能缺陷 → 提研发/厂家修复"),
    ("流程优化", 20, "卡单/流转不畅/规则不合理 → 流程改造/制度修订"),
    ("投诉咨询", 30, "政策咨询/口径误解/可解释投诉 → 引导手册/话术"),
    ("数据问题", 40, "状态不一致/批量数据错误 → 批量数据修复/核对"),
]

# 权威映射：二级场景 → 新一级（35 个场景全量覆盖）
L2_TO_L1 = {
    # 原计费与出账争议
    "多出账与费用突增": "系统问题",
    "已关闭仍扣费": "系统问题",
    "计费规则执行错误": "系统问题",
    "退费与账单争议": "投诉咨询",
    "复机与欠费状态异常": "数据问题",
    # 原营销与活动生效异常
    "营销案未生效": "系统问题",
    "活动时间未回传或错误": "数据问题",
    "优惠与权益未到账": "数据问题",
    # 原数据与状态异常
    "电视与机顶盒账号未同步": "数据问题",
    "业务状态多系统不一致": "数据问题",
    "业务在用显示未激活": "数据问题",
    "销户残留与逾期未清理": "数据问题",
    "实名与证件数据异常": "数据问题",
    "标准地址错乱或串号": "数据问题",
    # 原流程与工单卡单
    "施工单未触发": "流程优化",
    "装维待办找不到": "流程优化",
    "在途单阻塞新业务": "流程优化",
    "订单状态滞留未流转": "流程优化",
    "预受理与流程滞留": "流程优化",
    "归档与结单失败": "流程优化",
    "商机与合同查询不到": "流程优化",
    "跨地市审批不回传": "流程优化",
    # 原系统缺陷与办理受阻
    "接口报错与调用失败": "系统问题",
    "前端校验拦截或无法提交": "系统问题",
    "字段映射缺失或带不出": "系统问题",
    "撤单退单接口缺失": "系统问题",
    "超期自动归档打停业务": "系统问题",
    "仅能后台SQL修复": "系统问题",
    "数据串号与融合单异常": "系统问题",
    # 原外部依赖与协同
    "网络侧与厂家责任": "系统问题",
    "第三方平台同步异常": "数据问题",
    "跨部门协作等待": "流程优化",
    # 原操作与咨询
    "资费政策咨询": "投诉咨询",
    "查询与核实请求": "投诉咨询",
    "操作指引": "投诉咨询",
}

# 兜底：二级为空时按旧一级整体归入（取该旧类下多数场景性质）
L1_DEFAULT = {
    "计费与出账争议": "系统问题",
    "营销与活动生效异常": "数据问题",
    "数据与状态异常": "数据问题",
    "流程与工单卡单": "流程优化",
    "系统缺陷与办理受阻": "系统问题",
    "外部依赖与协同": "系统问题",
    "操作与咨询": "投诉咨询",
}


def _table_exists(conn, name: str) -> bool:
    return bool(
        conn.execute(
            text("SELECT COUNT(*) FROM information_schema.tables "
                 "WHERE table_schema=DATABASE() AND table_name=:n"),
            {"n": name},
        ).scalar()
    )


def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "pmwb_complaint_category"):
        return
    # 幂等：已迁移过则跳过
    new_done = conn.execute(
        text("SELECT COUNT(*) FROM pmwb_complaint_category WHERE level=1 AND name='系统问题'")
    ).scalar()
    old_left = conn.execute(
        text("SELECT COUNT(*) FROM pmwb_complaint_category WHERE level=1 AND name='计费与出账争议'")
    ).scalar()
    if new_done and not old_left:
        return

    # 1) 一级表重建：删旧 7 条，插新 4 条（keywords 置空——识别已改 LLM 主导，规则词库废弃）
    conn.execute(text("DELETE FROM pmwb_complaint_category WHERE level=1"))
    for name, sort_order, desc in NEW_L1:
        conn.execute(
            text("INSERT INTO pmwb_complaint_category(level, parent_name, name, keywords, sort_order, "
                 "enabled, note, created_at, updated_at) "
                 "VALUES(1, NULL, :name, NULL, :sort, 1, :note, NOW(), NOW())"),
            {"name": name, "sort": sort_order, "note": desc},
        )

    # 2) 二级表挂新一级 + sort_order 按新一级分组重排（组内按原 id 顺序，步长 10）
    order_base = {"系统问题": 100, "流程优化": 200, "投诉咨询": 300, "数据问题": 400}
    counters = {k: 0 for k in order_base}
    rows = conn.execute(
        text("SELECT id, name FROM pmwb_complaint_category WHERE level=2 ORDER BY sort_order, id")
    ).fetchall()
    for rid, name in rows:
        new_l1 = L2_TO_L1.get(name)
        if new_l1 is None:
            continue  # 未知场景保持原样，由人工在字典管理中调整
        counters[new_l1] += 10
        conn.execute(
            text("UPDATE pmwb_complaint_category SET parent_name=:p, sort_order=:s WHERE id=:i"),
            {"p": new_l1, "s": order_base[new_l1] + counters[new_l1], "i": rid},
        )

    # 3) 存量业务表改写 category_l1
    for table in ("pmwb_complaint_ticket", "pmwb_complaint_action", "pmwb_complaint_problem"):
        if not _table_exists(conn, table):
            continue
        # 3a) l2 非空且在映射内 → 按场景映射
        for l2, new_l1 in L2_TO_L1.items():
            conn.execute(
                text(f"UPDATE {table} SET category_l1=:l1 WHERE category_l2=:l2"),
                {"l1": new_l1, "l2": l2},
            )
        # 3b) l2 为空 → 按旧一级默认映射
        for old_l1, new_l1 in L1_DEFAULT.items():
            conn.execute(
                text(f"UPDATE {table} SET category_l1=:l1 "
                     f"WHERE category_l1=:old AND (category_l2 IS NULL OR category_l2='')"),
                {"l1": new_l1, "old": old_l1},
            )


def downgrade() -> None:
    # 数据迁移不支持自动回滚（映射不可逆），如需回滚手工恢复字典并重跑归类
    pass
