"""根因模式双字段解耦：root_cause（个案事实）与 root_pattern（受控模式）分离

背景（2026-11-04 老大拍板，见 docs/客诉根因聚类方法论.md）：
  实测 858 个有效簇里 776 个是「1 单 1 簇」（90.4%），但标题带 ≥6 位数字的只有 4.4%——
  碎片化的真因不是账号进了标题，而是**一段 L1 文本同时承担「个案事实」与「可复用模式」
  两个互相冲突的职责**。要具体到单，就必然碎。

处置：
  1. 工单层加 root_pattern（{对象}-{机制}，禁用户级信息）+ 三要素列
     rc_mechanism / rc_object / rc_trigger（受控枚举，见 constants/complaint_pattern.py）；
  2. 根因簇加 mechanism / biz_object / pattern_key（= 环节|机制|上位对象 三元组唯一键）；
  3. **历史数据不回填猜测值**：pattern 全为空，由 relabel_clusters 用 LLM 一次性标定后回填
     （簇级标注 ~22 批，比重跑 1476 单便宜 7 倍，且模型一次看 40 簇天然收敛）。

Revision ID: 20261104000007
Revises: 20261104000006
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104000007"
down_revision = "20261104000006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 工单层：L1 双字段解耦 ──
    op.add_column("pmwb_complaint_ticket", sa.Column(
        "root_pattern", sa.String(200), nullable=True,
        comment="可复用根因模式（{对象}-{机制}，禁用户级信息，L2 簇键唯一来源）"))
    op.add_column("pmwb_complaint_ticket", sa.Column(
        "rc_mechanism", sa.String(32), nullable=True,
        comment="失败机制（受控枚举，constants/complaint_pattern.py）"))
    op.add_column("pmwb_complaint_ticket", sa.Column(
        "rc_object", sa.String(32), nullable=True, comment="业务对象（受控枚举）"))
    op.add_column("pmwb_complaint_ticket", sa.Column(
        "rc_trigger", sa.String(64), nullable=True, comment="触发条件（短词，可空）"))

    # ── 簇层：三元组键 ──
    op.add_column("pmwb_complaint_rootcause", sa.Column(
        "mechanism", sa.String(32), nullable=True, comment="簇级失败机制（取簇内众数）"))
    op.add_column("pmwb_complaint_rootcause", sa.Column(
        "biz_object", sa.String(32), nullable=True, comment="簇级业务对象（取簇内众数）"))
    op.add_column("pmwb_complaint_rootcause", sa.Column(
        "pattern_key", sa.String(128), nullable=True,
        comment="簇唯一键：环节|机制|上位对象（唯一真相源 constants/complaint_pattern.pattern_key）"))

    op.create_index("idx_ct_pattern", "pmwb_complaint_ticket", ["root_pattern"])
    op.create_index("idx_ct_mechanism", "pmwb_complaint_ticket", ["rc_mechanism"])
    op.create_index("idx_crc_pattern_key", "pmwb_complaint_rootcause", ["pattern_key"])


def downgrade() -> None:
    op.drop_index("idx_crc_pattern_key", table_name="pmwb_complaint_rootcause")
    op.drop_index("idx_ct_mechanism", table_name="pmwb_complaint_ticket")
    op.drop_index("idx_ct_pattern", table_name="pmwb_complaint_ticket")
    for col in ("pattern_key", "biz_object", "mechanism"):
        op.drop_column("pmwb_complaint_rootcause", col)
    for col in ("rc_trigger", "rc_object", "rc_mechanism", "root_pattern"):
        op.drop_column("pmwb_complaint_ticket", col)
