"""客诉改进措施口径切根因簇（category_l2 降为快照）

背景：措施有效性原按 category_l2（二级现象场景）周单量算降幅，而该场景桶实测
平均 7.6 单/桶、最大桶混装 6 类不相关问题。按粗桶算降幅的结果是「修了 A 缺陷，
B 缺陷还在这个桶里出单」，降幅被稀释甚至反向（现有措施实测 -246.9% 即此原因）。
故措施有效性改为按根因簇单量计算。

新增字段：pmwb_complaint_action.rootcause_nos（覆盖的根因簇，逗号分隔）
category_l2 保留为统计快照，不再参与有效性计算。

Revision ID: 20261104000004
Revises: 20261104000003
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104000004"
down_revision = "20261104000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pmwb_complaint_action", sa.Column(
        "rootcause_nos", sa.String(512), nullable=True,
        comment="覆盖的根因簇编号（逗号分隔；有效性据此计算，取代 category_l2）"))


def downgrade() -> None:
    op.drop_column("pmwb_complaint_action", "rootcause_nos")
