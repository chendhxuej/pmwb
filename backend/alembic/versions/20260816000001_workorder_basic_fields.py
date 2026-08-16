"""workorder basic fields: dev_ticket title/planned_finish_date + meeting_action title

补齐工单「基本信息」契约硬缺口（对应工单统一优化方案 Phase 3）：
- 开发工单 PmwbDevTicket 缺「工单标题」「计划完成时间」 -> 新增 title / planned_finish_date
- 会议行动项 PmwbMeetingAction 缺「独立标题」（content 兼描述）-> 新增 title（为空回退 content）

加列方式（不加历史数据迁移、不改旧列/状态枚举），低风险；旧数据 title 为 NULL，
前端回退显示 content，后端 API 自动返回新字段。
"""
from alembic import op
import sqlalchemy as sa


revision = "20260816000001"
down_revision = "20260815000001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "pmwb_dev_ticket",
        sa.Column("title", sa.String(length=256), comment="工单标题"),
    )
    op.add_column(
        "pmwb_dev_ticket",
        sa.Column("planned_finish_date", sa.Date(), comment="计划完成时间"),
    )
    op.add_column(
        "pmwb_meeting_action",
        sa.Column("title", sa.String(length=256), comment="行动项标题（独立标题；为空时前端回退显示 content）"),
    )


def downgrade():
    op.drop_column("pmwb_meeting_action", "title")
    op.drop_column("pmwb_dev_ticket", "planned_finish_date")
    op.drop_column("pmwb_dev_ticket", "title")
