"""add business event semantics to pmwb_knowledge_link

kc4-1：为关联表增加 event_type/event_date/summary 三列，支撑业务时间线(kc4-3)
与主笔记 §8 变更轨迹自动生成。
存量 event_date 用 created_at 日期回填；event_type 按 source_type 推断默认值。

注意：并行任务 kc4-5（20260811000001_sql_script_domain_code）已先落地并应用到数据库，
本迁移接在其后（down_revision=20260811000001），形成线性链，避免双 head 分支。
"""
from alembic import op
import sqlalchemy as sa


revision = "20260812000001"
down_revision = "20260811000001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "pmwb_knowledge_link",
        sa.Column(
            "event_type",
            sa.String(length=64),
            nullable=True,
            comment="业务事件类型：requirement/meeting/operation/deliverable/rule/key_work/manual",
        ),
    )
    op.add_column(
        "pmwb_knowledge_link",
        sa.Column("event_date", sa.Date(), nullable=True, comment="业务发生日期"),
    )
    op.add_column(
        "pmwb_knowledge_link",
        sa.Column("summary", sa.Text(), nullable=True, comment="事件一句话摘要"),
    )
    op.create_index("idx_kl_event_date", "pmwb_knowledge_link", ["event_date"])

    # 存量回填：event_date 用 created_at 日期；event_type 按 source_type 推断默认值
    op.execute(
        "UPDATE pmwb_knowledge_link SET event_date = DATE(created_at) WHERE event_date IS NULL"
    )
    op.execute(
        "UPDATE pmwb_knowledge_link SET event_type = 'requirement' "
        "WHERE source_type = 'requirement' AND event_type IS NULL"
    )
    op.execute(
        "UPDATE pmwb_knowledge_link SET event_type = 'meeting' "
        "WHERE source_type = 'meeting' AND event_type IS NULL"
    )
    op.execute(
        "UPDATE pmwb_knowledge_link SET event_type = 'operation' "
        "WHERE source_type = 'operation' AND event_type IS NULL"
    )
    op.execute(
        "UPDATE pmwb_knowledge_link SET event_type = 'ticket' "
        "WHERE source_type = 'ticket' AND event_type IS NULL"
    )
    op.execute(
        "UPDATE pmwb_knowledge_link SET event_type = 'deliverable' "
        "WHERE source_type = 'deliverable' AND event_type IS NULL"
    )
    op.execute(
        "UPDATE pmwb_knowledge_link SET event_type = 'key_work' "
        "WHERE source_type = 'key_work' AND event_type IS NULL"
    )


def downgrade():
    op.drop_index("idx_kl_event_date", table_name="pmwb_knowledge_link")
    op.drop_column("pmwb_knowledge_link", "summary")
    op.drop_column("pmwb_knowledge_link", "event_date")
    op.drop_column("pmwb_knowledge_link", "event_type")
