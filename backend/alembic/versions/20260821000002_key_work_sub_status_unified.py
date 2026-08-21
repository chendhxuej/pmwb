"""重点工作子表状态统一为五态

将里程碑 / 月度计划 / 周计划 / 成员待办的状态统一扩展为：
not_started / in_progress / completed / cancelled / delayed

历史数据映射：
- pending -> not_started
- todo -> not_started
- done -> completed
- in_progress / cancelled / delayed 保持不变
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260821000002"
down_revision = "20260821000001"
branch_labels = None
depends_on = None


# 旧枚举值
OLD_MS_VALUES = ('pending', 'in_progress', 'done', 'delayed')
OLD_PLAN_VALUES = ('pending', 'done')
OLD_TASK_VALUES = ('todo', 'in_progress', 'done', 'cancelled')

# 新枚举值
NEW_VALUES = ('not_started', 'in_progress', 'completed', 'cancelled', 'delayed')

# 兼容过渡枚举值（新旧并存），用 dict.fromkeys 去重保留顺序
TRANSITION_MS_VALUES = tuple(dict.fromkeys((*OLD_MS_VALUES, *NEW_VALUES)))
TRANSITION_PLAN_VALUES = tuple(dict.fromkeys((*OLD_PLAN_VALUES, *NEW_VALUES)))
TRANSITION_TASK_VALUES = tuple(dict.fromkeys((*OLD_TASK_VALUES, *NEW_VALUES)))


def _enum_type(values):
    return sa.Enum(*values)


def upgrade() -> None:
    # 1) 先扩展枚举，允许新旧值共存，避免 UPDATE 时因 enum 不包含新值而失败
    op.alter_column(
        'pmwb_key_work_milestone',
        'status',
        existing_type=mysql.ENUM(*OLD_MS_VALUES, collation='utf8mb4_unicode_ci'),
        type_=_enum_type(TRANSITION_MS_VALUES),
        existing_nullable=True,
        existing_server_default=sa.text("'pending'"),
        existing_comment='状态',
    )
    op.alter_column(
        'pmwb_key_work_monthly_plan',
        'status',
        existing_type=mysql.ENUM(*OLD_PLAN_VALUES, collation='utf8mb4_unicode_ci'),
        type_=_enum_type(TRANSITION_PLAN_VALUES),
        existing_nullable=True,
        existing_server_default=sa.text("'pending'"),
        existing_comment='状态',
    )
    op.alter_column(
        'pmwb_key_work_weekly_plan',
        'status',
        existing_type=mysql.ENUM(*OLD_PLAN_VALUES, collation='utf8mb4_unicode_ci'),
        type_=_enum_type(TRANSITION_PLAN_VALUES),
        existing_nullable=True,
        existing_server_default=sa.text("'pending'"),
        existing_comment='状态',
    )
    op.alter_column(
        'pmwb_key_work_member_task',
        'status',
        existing_type=mysql.ENUM(*OLD_TASK_VALUES, collation='utf8mb4_unicode_ci'),
        type_=_enum_type(TRANSITION_TASK_VALUES),
        existing_nullable=True,
        existing_server_default=sa.text("'todo'"),
        existing_comment='状态',
    )

    # 2) 迁移历史数据
    op.execute("""
        UPDATE pmwb_key_work_milestone
        SET status = CASE status
            WHEN 'pending' THEN 'not_started'
            WHEN 'done' THEN 'completed'
            ELSE status
        END
    """)
    op.execute("""
        UPDATE pmwb_key_work_monthly_plan
        SET status = CASE status
            WHEN 'pending' THEN 'not_started'
            WHEN 'done' THEN 'completed'
            ELSE status
        END
    """)
    op.execute("""
        UPDATE pmwb_key_work_weekly_plan
        SET status = CASE status
            WHEN 'pending' THEN 'not_started'
            WHEN 'done' THEN 'completed'
            ELSE status
        END
    """)
    op.execute("""
        UPDATE pmwb_key_work_member_task
        SET status = CASE status
            WHEN 'todo' THEN 'not_started'
            WHEN 'done' THEN 'completed'
            ELSE status
        END
    """)

    # 3) 收缩枚举为新的统一五态，并同步默认值
    op.alter_column(
        'pmwb_key_work_milestone',
        'status',
        existing_type=_enum_type(TRANSITION_MS_VALUES),
        type_=_enum_type(NEW_VALUES),
        existing_nullable=True,
        existing_server_default=sa.text("'not_started'"),
        existing_comment='状态',
    )
    op.alter_column(
        'pmwb_key_work_monthly_plan',
        'status',
        existing_type=_enum_type(TRANSITION_PLAN_VALUES),
        type_=_enum_type(NEW_VALUES),
        existing_nullable=True,
        existing_server_default=sa.text("'not_started'"),
        existing_comment='状态',
    )
    op.alter_column(
        'pmwb_key_work_weekly_plan',
        'status',
        existing_type=_enum_type(TRANSITION_PLAN_VALUES),
        type_=_enum_type(NEW_VALUES),
        existing_nullable=True,
        existing_server_default=sa.text("'not_started'"),
        existing_comment='状态',
    )
    op.alter_column(
        'pmwb_key_work_member_task',
        'status',
        existing_type=_enum_type(TRANSITION_TASK_VALUES),
        type_=_enum_type(NEW_VALUES),
        existing_nullable=True,
        existing_server_default=sa.text("'not_started'"),
        existing_comment='状态',
    )


def downgrade() -> None:
    # 1) 先扩展枚举，允许新旧值共存
    op.alter_column(
        'pmwb_key_work_milestone',
        'status',
        existing_type=_enum_type(NEW_VALUES),
        type_=_enum_type(TRANSITION_MS_VALUES),
        existing_nullable=True,
        existing_server_default=sa.text("'not_started'"),
        existing_comment='状态',
    )
    op.alter_column(
        'pmwb_key_work_monthly_plan',
        'status',
        existing_type=_enum_type(NEW_VALUES),
        type_=_enum_type(TRANSITION_PLAN_VALUES),
        existing_nullable=True,
        existing_server_default=sa.text("'not_started'"),
        existing_comment='状态',
    )
    op.alter_column(
        'pmwb_key_work_weekly_plan',
        'status',
        existing_type=_enum_type(NEW_VALUES),
        type_=_enum_type(TRANSITION_PLAN_VALUES),
        existing_nullable=True,
        existing_server_default=sa.text("'not_started'"),
        existing_comment='状态',
    )
    op.alter_column(
        'pmwb_key_work_member_task',
        'status',
        existing_type=_enum_type(NEW_VALUES),
        type_=_enum_type(TRANSITION_TASK_VALUES),
        existing_nullable=True,
        existing_server_default=sa.text("'not_started'"),
        existing_comment='状态',
    )

    # 2) 反向迁移历史数据
    op.execute("""
        UPDATE pmwb_key_work_milestone
        SET status = CASE status
            WHEN 'not_started' THEN 'pending'
            WHEN 'completed' THEN 'done'
            ELSE status
        END
    """)
    op.execute("""
        UPDATE pmwb_key_work_monthly_plan
        SET status = CASE status
            WHEN 'not_started' THEN 'pending'
            WHEN 'completed' THEN 'done'
            WHEN 'cancelled' THEN 'pending'
            WHEN 'delayed' THEN 'pending'
            WHEN 'in_progress' THEN 'pending'
            ELSE status
        END
    """)
    op.execute("""
        UPDATE pmwb_key_work_weekly_plan
        SET status = CASE status
            WHEN 'not_started' THEN 'pending'
            WHEN 'completed' THEN 'done'
            WHEN 'cancelled' THEN 'pending'
            WHEN 'delayed' THEN 'pending'
            WHEN 'in_progress' THEN 'pending'
            ELSE status
        END
    """)
    op.execute("""
        UPDATE pmwb_key_work_member_task
        SET status = CASE status
            WHEN 'not_started' THEN 'todo'
            WHEN 'completed' THEN 'done'
            WHEN 'cancelled' THEN 'cancelled'
            WHEN 'delayed' THEN 'todo'
            WHEN 'in_progress' THEN 'in_progress'
            ELSE status
        END
    """)

    # 3) 收缩为旧枚举
    op.alter_column(
        'pmwb_key_work_milestone',
        'status',
        existing_type=_enum_type(TRANSITION_MS_VALUES),
        type_=mysql.ENUM(*OLD_MS_VALUES, collation='utf8mb4_unicode_ci'),
        existing_nullable=True,
        existing_server_default=sa.text("'pending'"),
        existing_comment='状态',
    )
    op.alter_column(
        'pmwb_key_work_monthly_plan',
        'status',
        existing_type=_enum_type(TRANSITION_PLAN_VALUES),
        type_=mysql.ENUM(*OLD_PLAN_VALUES, collation='utf8mb4_unicode_ci'),
        existing_nullable=True,
        existing_server_default=sa.text("'pending'"),
        existing_comment='状态',
    )
    op.alter_column(
        'pmwb_key_work_weekly_plan',
        'status',
        existing_type=_enum_type(TRANSITION_PLAN_VALUES),
        type_=mysql.ENUM(*OLD_PLAN_VALUES, collation='utf8mb4_unicode_ci'),
        existing_nullable=True,
        existing_server_default=sa.text("'pending'"),
        existing_comment='状态',
    )
    op.alter_column(
        'pmwb_key_work_member_task',
        'status',
        existing_type=_enum_type(TRANSITION_TASK_VALUES),
        type_=mysql.ENUM(*OLD_TASK_VALUES, collation='utf8mb4_unicode_ci'),
        existing_nullable=True,
        existing_server_default=sa.text("'todo'"),
        existing_comment='状态',
    )
