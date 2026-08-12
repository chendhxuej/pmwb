"""business domain hierarchy refactor

Revision ID: 20260805000002
Revises: 20260805000001
Create Date: 2026-08-05 21:00:00

给 pmwb_business_domain 表新增 description 列，并将种子数据重构为
商客业务/政企业务/系统平台三级层级结构。
"""
from alembic import op
import sqlalchemy as sa

revision = "20260805000002"
down_revision = "20260805000001"
branch_labels = None
depends_on = None


def upgrade():
    # 1. 新增 description 列
    op.add_column("pmwb_business_domain", sa.Column("description", sa.Text(), nullable=True, comment="业务领域描述/说明"))

    # 2. 添加外键约束（parent_id → id，已有索引但缺 FK）
    try:
        op.create_foreign_key("fk_bd_parent", "pmwb_business_domain", "pmwb_business_domain", ["parent_id"], ["id"])
    except Exception:
        pass  # FK 可能已存在

    # 3. 清空旧种子数据（保留表结构）
    op.execute("DELETE FROM pmwb_business_domain")

    # 4. 插入新层级种子数据
    # 格式：(domain_code, domain_name, domain_group, vault_path, parent_code, sort_order, description, enabled)
    # parent_code 为父领域 domain_code，NULL = 一级大类
    seed = [
        # ====== 一级大类 ======
        ("commercial-group", "商客业务", "商客业务", "01-业务知识/政企业务知识库/商客业务", None, 10, "集团商客市场政企产品核心业务线", True),
        ("enterprise-group", "政企业务", "政企业务", "01-业务知识/政企业务知识库", None, 20, "商客以外的政企业务线（专线/短信/卫星等）", True),
        ("platform-group", "系统平台", "系统平台", None, None, 30, "政企系统建设与运营（工作台/订单中心/电子协议）", True),
        ("general-group", "通用", "通用", None, None, 90, "非特定业务线的通用分类", True),

        # ====== 商客业务 → 二级细分 ======
        ("ywt-broadband", "一网通宽带", "商客业务", "01-业务知识/政企业务知识库/商客业务/一网通宽带", "commercial-group", 11, "商客融合/统一入口类宽带产品", True),
        ("ftto", "FTTO", "商客业务", "01-业务知识/政企业务知识库/商客业务/FTTO", "commercial-group", 12, "光纤到办公室/小微企业场景", True),
        ("security", "商客安防", "商客业务", "01-业务知识/政企业务知识库/商客业务/安防", "commercial-group", 13, "商客安防类产品", True),
        ("commercial-saas", "商客SaaS", "商客业务", "01-业务知识/政企业务知识库/商客业务/商客SaaS", "commercial-group", 14, "商客SaaS业务产品", True),
        ("iptv", "宽带电视", "商客业务", "01-业务知识/政企业务知识库/商客业务/宽带电视", "commercial-group", 15, "宽带电视/IPTV业务", True),
        ("fusion-provisioning", "融合开通", "商客业务", "01-业务知识/政企业务知识库/商客业务/融合开通", "commercial-group", 16, "融合开通流程升级", True),
        ("group-order-delivery", "团单交付", "商客业务", "01-业务知识/政企业务知识库/商客业务/团单交付", "commercial-group", 17, "团单交付流程升级", True),
        ("commercial-zone", "商客专区运营", "商客业务", "01-业务知识/政企业务知识库/商客业务/商客专区", "commercial-group", 18, "商客专区运营与26年试点（智能生成/匹配/报价）", True),

        # ====== 政企业务 → 二级细分 ======
        ("dedicated-line", "专线", "政企业务", "01-业务知识/政企业务知识库/专线业务", "enterprise-group", 21, "数据专线/MPLS VPN/VPDN/互联网专线等", True),
        ("group-sms", "集团短信", "政企业务", "01-业务知识/政企业务知识库/集团短信业务", "enterprise-group", 22, "集团短信-实名制/产品", True),
        ("satellite-broadband", "卫星宽带", "政企业务", "01-业务知识/政企业务知识库/卫星宽带", "enterprise-group", 23, "卫星宽带业务", True),
        ("international", "国际业务", "政企业务", "01-业务知识/政企业务知识库/国际业务", "enterprise-group", 24, "国际专线/跨境业务", True),
        ("railway", "国铁项目", "政企业务", "01-业务知识/政企业务知识库/国铁项目", "enterprise-group", 25, "国铁项目专项", True),

        # ====== 系统平台 → 二级细分 ======
        ("gov-enterprise-workbench", "政企工作台", "系统平台", "01-业务知识/政企业务知识库/业务平台/政企工作台", "platform-group", 31, "政企工作台系统建设与运营", True),
        ("order-center", "订单中心", "系统平台", "01-业务知识/政企业务知识库/业务平台/订单中心", "platform-group", 32, "订单中心系统建设与运营", True),
        ("e-contract", "电子协议", "系统平台", "01-业务知识/政企业务知识库/业务平台/电子协议平台", "platform-group", 33, "电子协议系统平台建设与运营", True),

        # ====== 通用 → 二级细分 ======
        ("general", "综合/通用", "通用", None, "general-group", 91, "不归属特定业务线的事项", True),
        ("system-construction", "系统建设", "通用", None, "general-group", 92, "PMWB等内部系统建设", True),
    ]

    # 先插入一级大类（parent_code=NULL），记录 id
    parent_ids = {}
    for code, name, group, vp, _, so, desc, enabled in seed:
        if _ is None:
            # 一级大类
            op.execute(
                sa.text(
                    "INSERT INTO pmwb_business_domain (domain_code, domain_name, domain_group, vault_path, parent_id, sort_order, description, enabled) "
                    "VALUES (:code, :name, :grp, :vp, NULL, :so, :desc, :en)"
                ).bindparams(code=code, name=name, grp=group, vp=vp, so=so, desc=desc, en=int(enabled))
            )

    # 查出已插入的一级大类 id
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, domain_code FROM pmwb_business_domain WHERE parent_id IS NULL")).fetchall()
    for rid, rcode in rows:
        parent_ids[rcode] = rid

    # 插入二级细分
    for code, name, group, vp, parent_code, so, desc, enabled in seed:
        if parent_code is not None:
            pid = parent_ids.get(parent_code)
            if pid:
                op.execute(
                    sa.text(
                        "INSERT INTO pmwb_business_domain (domain_code, domain_name, domain_group, vault_path, parent_id, sort_order, description, enabled) "
                        "VALUES (:code, :name, :grp, :vp, :pid, :so, :desc, :en)"
                    ).bindparams(code=code, name=name, grp=group, vp=vp, pid=pid, so=so, desc=desc, en=int(enabled))
                )


def downgrade():
    op.drop_constraint("fk_bd_parent", "pmwb_business_domain", type_="foreignkey")
    op.drop_column("pmwb_business_domain", "description")
