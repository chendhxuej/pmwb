"""根因簇增加「是否缺陷」标记，咨询类簇不进问题台账

背景（老大 2026-11-04 拍板）：历史数据补导后根因库出现一个 109 单的
「非系统缺陷-使用咨询」垃圾桶簇（RC-0618，另有若干 fault_stage=使用咨询 的小簇），
这些是业务/操作咨询，不是系统缺陷，混进共性问题台账会把压降空间算虚。

处置：给簇加 is_defect 标记（默认 1=缺陷），fault_stage='使用咨询' 的簇回填为 0，
问题识别（scan_candidates）跳过 is_defect=0 的簇；这些单仍在根因库可见、计入
「咨询类」统计，只是不生成台账候选。

Revision ID: 20261104000005
Revises: 20261104000004
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104000005"
down_revision = "20261104000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pmwb_complaint_rootcause",
        sa.Column("is_defect", sa.SmallInteger(), nullable=False,
                  server_default="1", comment="是否系统缺陷：1=是，0=咨询/非缺陷（不进台账）"),
    )
    # 回填：使用咨询类不算缺陷
    op.execute(
        "UPDATE pmwb_complaint_rootcause SET is_defect = 0 "
        "WHERE fault_stage = '使用咨询'"
    )


def downgrade() -> None:
    op.drop_column("pmwb_complaint_rootcause", "is_defect")
