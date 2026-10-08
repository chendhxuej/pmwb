"""状态列 ENUM → VARCHAR(32)：支持后续新增状态零迁移

背景（任务中心「就地切换状态 + 工单状态标准化」方案）：
  各业务表的状态列原为 MySQL 原生 ENUM，新增一个状态值必须 ALTER TABLE，
  与「状态注册表为唯一真相源、新增状态无需迁移」的目标冲突。
  本迁移把 11 张表的状态列统一改为 VARCHAR(32)，合法值校验下沉到
  `backend/constants/status_registry.py`。

写法参照项目既有先例：alembic/versions/768014c30bda_meeting_action_status_varchar.py
（该表 pmwb_meeting_action.status 已是 VARCHAR(32)，本迁移不再包含）。

幂等性：upgrade/downgrade 均先探测当前列类型，已是目标类型则跳过，
因此可安全重复执行（本环境 alembic_version 戳位与脚本链存在历史漂移）。

Revision ID: 20261008000001
Revises: 20260914000002
Create Date: 2026-10-08

注：脚本目录里 20260917000001（email_records 加 ref_type/ref_id）在本机数据库
    为「未戳位但列已存在」的历史漂移，故本迁移挂在实际已应用的 20260914000002 之后。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20261008000001"
down_revision: Union[str, None] = "20260914000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (表名, 列名, 原 ENUM 取值元组, 默认值)
STATUS_COLUMNS = (
    ("pmwb_todo", "status", ("todo", "in_progress", "done", "cancelled"), "todo"),
    (
        "pmwb_operation_issue",
        "status",
        ("pending", "processing", "verify", "resolved", "closed", "suspended"),
        "pending",
    ),
    (
        "pmwb_research_issue",
        "status",
        ("pending", "processing", "verify", "resolved", "closed", "suspended"),
        "pending",
    ),
    (
        "pmwb_dev_ticket",
        "status",
        ("created", "design_reviewed", "dev_completed", "test_completed", "live", "archived"),
        "created",
    ),
    ("pmwb_active_optimization", "status", ("pending", "adopted", "rejected"), "pending"),
    ("pmwb_meeting", "status", ("planned", "held", "cancelled", "not_attended"), "planned"),
    (
        "pmwb_key_work",
        "status",
        ("planning", "in_progress", "completed", "paused", "cancelled"),
        "planning",
    ),
    (
        "pmwb_key_work_milestone",
        "status",
        ("not_started", "in_progress", "completed", "cancelled", "delayed"),
        "not_started",
    ),
    (
        "pmwb_key_work_monthly_plan",
        "status",
        ("not_started", "in_progress", "completed", "cancelled", "delayed"),
        "not_started",
    ),
    (
        "pmwb_key_work_weekly_plan",
        "status",
        ("not_started", "in_progress", "completed", "cancelled", "delayed"),
        "not_started",
    ),
    (
        "pmwb_key_work_member_task",
        "status",
        ("not_started", "in_progress", "completed", "cancelled", "delayed"),
        "not_started",
    ),
)


def _current_col(bind, table: str, column: str):
    """返回列的 {type_str, comment}；表/列不存在返回 None。"""
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return None
    for col in insp.get_columns(table):
        if col["name"] == column:
            return {"type": str(col["type"]).lower(), "comment": col.get("comment") or ""}
    return None


def _alter(bind, table, column, old_values, default, to_varchar: bool):
    info = _current_col(bind, table, column)
    if info is None:
        return  # 表/列不存在（create_all 尚未建）→ 跳过
    cur = info["type"]
    is_varchar = "char" in cur
    if to_varchar and is_varchar:
        return  # 已是 VARCHAR → 幂等跳过
    if (not to_varchar) and cur.startswith("enum"):
        return  # 已是 ENUM → 幂等跳过
    # MySQL 的 MODIFY COLUMN 会整体重写列定义（含注释），故显式保留原注释。
    existing = sa.String(length=32) if (not to_varchar) else sa.Enum(*old_values)
    target = sa.Enum(*old_values) if (not to_varchar) else sa.String(length=32)
    op.alter_column(
        table,
        column,
        existing_type=existing,
        type_=target,
        existing_nullable=True,
        existing_server_default=sa.text(f"'{default}'"),
        server_default=sa.text(f"'{default}'"),
        existing_comment=info["comment"],
        comment=info["comment"],
    )


def upgrade() -> None:
    bind = op.get_bind()
    for table, column, old_values, default in STATUS_COLUMNS:
        _alter(bind, table, column, old_values, default, to_varchar=True)


def downgrade() -> None:
    """回退为 ENUM。注意：若库中已写入 ENUM 之外的新状态值，MySQL 严格模式下会失败，
    需先清理这些值——属有损回退，注释说明。"""
    bind = op.get_bind()
    for table, column, old_values, default in STATUS_COLUMNS:
        _alter(bind, table, column, old_values, default, to_varchar=False)
