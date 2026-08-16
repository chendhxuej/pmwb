"""fix utc to cst: created_at/updated_at +8h

全局时区根治：models.py 所有 created_at/updated_at 原用 datetime.utcnow（UTC 存储），
现已改为 now_cn()（UTC+8）。本迁移将存量 UTC 数据统一 +8 小时，使旧数据与新代码一致。

排除 sent_emails（Node.js 遗留表，created_at 已是本地时间）。
其余 pmwb_* / email_records / sa_info 均为 SQLAlchemy 创建，created_at 为 UTC。

使用 inspector 动态检测列是否存在，避免硬编码。
"""
from alembic import op
from sqlalchemy import inspect, text

revision = "20260816000002"
down_revision = "20260816000001"
branch_labels = None
depends_on = None

# 排除 Node.js 遗留表（已是本地时间）
_EXCLUDE = {"sent_emails"}

# 所有 models.py 中定义的表名
_TABLES = [
    "pmwb_requirement_ext",
    "pmwb_user_story",
    "pmwb_dev_ticket",
    "pmwb_dev_deliverable",
    "pmwb_dev_ticket_log",
    "pmwb_todo",
    "pmwb_operation_issue",
    "pmwb_operation_analysis",
    "pmwb_meeting",
    "pmwb_meeting_agenda",
    "pmwb_meeting_attendee",
    "pmwb_meeting_action",
    "pmwb_business_domain",
    "pmwb_knowledge_item",
    "pmwb_knowledge_link",
    "pmwb_requirement_evaluation",
    "email_records",
    "sa_info",
    "pmwb_key_work",
    "pmwb_key_work_goal",
    "pmwb_key_work_milestone",
    "pmwb_key_work_member",
    "pmwb_key_work_monthly_plan",
    "pmwb_key_work_weekly_plan",
    "pmwb_key_work_progress",
    "pmwb_key_work_member_task",
    "pmwb_key_work_deliverable",
    "pmwb_sql_script",
    "pmwb_org",
    "pmwb_staff",
    "pmwb_work_report",
    "pmwb_llm_provider",
]


def _shift(bind, hours: int):
    inspector = inspect(bind)
    for table_name in _TABLES:
        if table_name in _EXCLUDE:
            continue
        if table_name not in inspector.get_table_names():
            continue
        cols = {c["name"] for c in inspector.get_columns(table_name)}
        sign = "+" if hours > 0 else "-"
        h = abs(hours)
        for col in ("created_at", "updated_at"):
            if col in cols:
                sql = (
                    f"UPDATE `{table_name}` "
                    f"SET `{col}` = DATE_ADD(`{col}`, INTERVAL {h} HOUR) "
                    f"WHERE `{col}` IS NOT NULL"
                )
                bind.execute(text(sql))
                print(f"  {table_name}.{col} {sign}{h}h done")


def upgrade():
    bind = op.get_bind()
    print("Migrating UTC timestamps to UTC+8 (skip sent_emails)...")
    _shift(bind, +8)
    print("Done.")


def downgrade():
    bind = op.get_bind()
    print("Reverting UTC+8 timestamps back to UTC (skip sent_emails)...")
    _shift(bind, -8)
    print("Done.")
