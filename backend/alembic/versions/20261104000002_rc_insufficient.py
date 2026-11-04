"""客诉工单根因分析全自动：rc_status 弃用「待人工」，改「信息不足」

原则变更（2026-11-04 老大拍板）：工单内容分析必须 AI 全自动，不得有人工队列。
门禁不通过的单即以 rc_status='insufficient' 入库，并记录缺口原因（rc_gap），
聚合时单列「信息不足」桶、不计入根因分布分母——宁标不足，也不把粗结论混进统计。

Revision ID: 20261104000002
Revises: 20261104000001
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104000002"
down_revision = "20261104000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pmwb_complaint_ticket", sa.Column(
        "rc_gap", sa.String(255), nullable=True,
        comment="根因信息缺口（rc_status=insufficient 时记录缺什么，如“缺处理意见/无具体报错”）"))
    op.get_bind().execute(sa.text(
        "UPDATE pmwb_complaint_ticket SET rc_status = 'insufficient' WHERE rc_status = 'low'"))


def downgrade() -> None:
    op.get_bind().execute(sa.text(
        "UPDATE pmwb_complaint_ticket SET rc_status = 'low' WHERE rc_status = 'insufficient'"))
    op.drop_column("pmwb_complaint_ticket", "rc_gap")
