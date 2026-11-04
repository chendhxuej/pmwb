"""客诉问题台账锚点切根因簇 + 工单已知/新增判定字段

背景（2026-11-04 老大拍板）：
  问题台账原以 category_l2（二级现象场景）为归并锚点，而该级实测 30 个桶承载
  228 单（平均 7.6 单/桶），最大桶 38 单混装 6 类不相关问题。用粗桶做问题实体，
  问题必然失真、台账必然空转（改前仅 3 条候选）。上轮已完成每单根因细化，
  故本迁移把问题实体锚到根因簇（rootcause_no），并给工单加「已知/新增」判定字段。

新增字段：
  pmwb_complaint_problem.rootcause_no   主簇指针（问题=一组同机制根因簇）
  pmwb_complaint_problem.rootcause_nos  覆盖的全部簇（逗号分隔，一问题可纳多簇）
  pmwb_complaint_ticket.known_flag      1=已知问题（命中在办问题） 0=新增问题
  pmwb_complaint_ticket.known_problem_no 命中的在办问题编号（known_flag=1 时有值）

Revision ID: 20261104000003
Revises: 20261104000002
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104000003"
down_revision = "20261104000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pmwb_complaint_problem", sa.Column(
        "rootcause_no", sa.String(64), nullable=True,
        comment="主根因簇编号（问题实体锚点；取代 category_l2 作归并键）"))
    op.add_column("pmwb_complaint_problem", sa.Column(
        "rootcause_nos", sa.String(512), nullable=True,
        comment="覆盖的根因簇编号（逗号分隔，一问题可纳入多个近义簇）"))
    op.add_column("pmwb_complaint_ticket", sa.Column(
        "known_flag", sa.SmallInteger, nullable=True,
        comment="已知/新增判定：1=命中在办问题（已知） 0=新增问题"))
    op.add_column("pmwb_complaint_ticket", sa.Column(
        "known_problem_no", sa.String(64), nullable=True,
        comment="命中的在办问题编号（known_flag=1 时有值）"))

    op.create_index("idx_cp_rc", "pmwb_complaint_problem", ["rootcause_no"])
    op.create_index("idx_ct_known", "pmwb_complaint_ticket", ["known_flag"])


def downgrade() -> None:
    op.drop_index("idx_ct_known", table_name="pmwb_complaint_ticket")
    op.drop_index("idx_cp_rc", table_name="pmwb_complaint_problem")
    op.drop_column("pmwb_complaint_ticket", "known_problem_no")
    op.drop_column("pmwb_complaint_ticket", "known_flag")
    op.drop_column("pmwb_complaint_problem", "rootcause_nos")
    op.drop_column("pmwb_complaint_problem", "rootcause_no")
