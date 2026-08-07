"""business domain and knowledge linkage

Revision ID: 20260805000001
Revises: 20260804000002
Create Date: 2026-08-05 14:00:00

新增业务领域字典表 pmwb_business_domain，并给知识索引表和 5 个业务表
增加 domain_code 列，建立统一的业务关联维度。
"""
from alembic import op
import sqlalchemy as sa

revision = "20260805000001"
down_revision = "20260804000002"
branch_labels = None
depends_on = None


def upgrade():
    # 1. 创建业务领域字典表
    op.create_table(
        "pmwb_business_domain",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("domain_code", sa.String(64), nullable=False, comment="业务线编码"),
        sa.Column("domain_name", sa.String(128), nullable=False, comment="业务线中文名"),
        sa.Column("domain_group", sa.String(64), nullable=False, server_default="政企业务", comment="业务大类"),
        sa.Column("vault_path", sa.String(512), nullable=True, comment="Obsidian vault 内相对目录路径"),
        sa.Column("parent_id", sa.Integer(), nullable=True, comment="父领域ID"),
        sa.Column("sort_order", sa.Integer(), server_default="0", comment="排序号"),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("1"), comment="是否启用"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("domain_code"),
        comment="业务领域字典表",
    )
    op.create_index("idx_bd_group", "pmwb_business_domain", ["domain_group"])
    op.create_index("idx_bd_parent", "pmwb_business_domain", ["parent_id"])

    # 2. 知识索引表加 domain_code
    op.add_column("pmwb_knowledge_item", sa.Column("domain_code", sa.String(64), nullable=True, comment="关联业务领域编码"))
    op.create_index("idx_knowledge_domain", "pmwb_knowledge_item", ["domain_code"])

    # 3. 五个业务表加 domain_code
    op.add_column("pmwb_requirement_ext", sa.Column("domain_code", sa.String(64), nullable=True, comment="关联业务领域编码"))
    op.add_column("pmwb_dev_ticket", sa.Column("domain_code", sa.String(64), nullable=True, comment="关联业务领域编码"))
    op.add_column("pmwb_operation_issue", sa.Column("domain_code", sa.String(64), nullable=True, comment="关联业务领域编码"))
    op.add_column("pmwb_meeting", sa.Column("domain_code", sa.String(64), nullable=True, comment="关联业务领域编码"))
    op.add_column("pmwb_key_work", sa.Column("domain_code", sa.String(64), nullable=True, comment="关联业务领域编码"))

    # 4. 初始化业务领域种子数据
    seed_data = [
        # (domain_code, domain_name, domain_group, vault_path, parent_id, sort_order)
        ("commercial-saas", "商客SaaS", "政企业务", "01-业务知识/政企业务知识库/商客业务", None, 1),
        ("ywt-broadband", "一网通宽带", "政企业务", "01-业务知识/政企业务知识库/商客业务", None, 2),
        ("ftto", "FTTO", "政企业务", "01-业务知识/政企业务知识库/商客业务", None, 3),
        ("security", "商客安防", "政企业务", "01-业务知识/政企业务知识库/商客业务", None, 4),
        ("dedicated-line", "专线", "政企业务", "01-业务知识/政企业务知识库/专线业务", None, 10),
        ("group-sms", "集团短信", "政企业务", "01-业务知识/政企业务知识库/集团短信业务", None, 20),
        ("e-contract", "电子协议", "政企业务", "01-业务知识/政企业务知识库/业务平台/电子协议平台", None, 30),
        ("satellite-broadband", "卫星宽带", "政企业务", "01-业务知识/政企业务知识库/卫星宽带", None, 40),
        ("international", "国际业务", "政企业务", "01-业务知识/政企业务知识库/国际业务", None, 50),
        ("railway", "国铁项目", "政企业务", "01-业务知识/政企业务知识库/国铁项目", None, 60),
        ("general", "通用", "通用", None, None, 100),
        ("system-construction", "系统建设", "通用", None, None, 101),
    ]
    for code, name, group, vault_path, parent_id, sort_order in seed_data:
        op.execute(
            sa.text(
                "INSERT INTO pmwb_business_domain (domain_code, domain_name, domain_group, vault_path, parent_id, sort_order, enabled) "
                "VALUES (:code, :name, :grp, :vp, :pid, :so, 1)"
            ).bindparams(
                code=code, name=name, grp=group, vp=vault_path, pid=parent_id, so=sort_order,
            )
        )


def downgrade():
    op.drop_column("pmwb_key_work", "domain_code")
    op.drop_column("pmwb_meeting", "domain_code")
    op.drop_column("pmwb_operation_issue", "domain_code")
    op.drop_column("pmwb_dev_ticket", "domain_code")
    op.drop_column("pmwb_requirement_ext", "domain_code")

    op.drop_index("idx_knowledge_domain", table_name="pmwb_knowledge_item")
    op.drop_column("pmwb_knowledge_item", "domain_code")

    op.drop_index("idx_bd_parent", table_name="pmwb_business_domain")
    op.drop_index("idx_bd_group", table_name="pmwb_business_domain")
    op.drop_table("pmwb_business_domain")
