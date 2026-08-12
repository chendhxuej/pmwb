"""business domain match_keywords

Revision ID: 20260805000003
Revises: 20260805000002
Create Date: 2026-08-05 22:00:00

给 pmwb_business_domain 表新增 match_keywords 列，并为商客业务二级细分
写入分类关键词，用于 vault 反向同步时按文件名/标题将扁平笔记归入细分业务。
"""
from alembic import op
import sqlalchemy as sa

revision = "20260805000003"
down_revision = "20260805000002"
branch_labels = None
depends_on = None


def upgrade():
    # 1. 新增 match_keywords 列
    op.add_column(
        "pmwb_business_domain",
        sa.Column(
            "match_keywords",
            sa.String(512),
            nullable=True,
            comment="分类关键词（逗号分隔）；用于将扁平笔记按文件名/标题归入该细分业务",
        ),
    )

    # 2. 为商客业务二级细分写入分类关键词（匹配 01-业务知识/政企业务知识库/商客业务 下的扁平 .md 文件名）
    keywords = {
        "ywt-broadband": "一网通,集客一网通",
        "ftto": "FTTO",
        "security": "安防",
        "commercial-saas": "SaaS,e企赢客,小微ICT",
        "iptv": "互联网电视,IPTV",
        "fusion-provisioning": "融合,1+N+N",
        "group-order-delivery": "团单,交付",
        "commercial-zone": "商客专区,专区",
    }
    for code, kw in keywords.items():
        op.execute(
            sa.text(
                "UPDATE pmwb_business_domain SET match_keywords = :kw WHERE domain_code = :code"
            ).bindparams(kw=kw, code=code)
        )


def downgrade():
    op.drop_column("pmwb_business_domain", "match_keywords")
