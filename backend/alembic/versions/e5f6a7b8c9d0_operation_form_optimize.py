"""运营工单录单优化：子类重定义 / 责任人多选 / 影响范围改名

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-16 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # 0) 先把 issue_type 改为 VARCHAR，避免旧枚举约束导致数据映射失败
    bind.execute(
        sa.text(
            "ALTER TABLE pmwb_operation_issue MODIFY COLUMN issue_type "
            "VARCHAR(32) NULL DEFAULT 'other' COMMENT '问题子类(细分类型)'"
        )
    )
    # 1) 旧 issue_type 值映射到新枚举
    bind.execute(
        sa.text(
            """
            UPDATE pmwb_operation_issue SET issue_type = CASE issue_type
                WHEN 'data_error' THEN 'data_abnormal'
                WHEN 'system_failure' THEN 'bug'
                WHEN 'performance' THEN 'bug'
                WHEN 'complaint' THEN 'other'
                WHEN 'process_block' THEN 'other'
                ELSE 'other' END
            """
        )
    )
    # 2) 子类枚举重定义为新 6 项
    bind.execute(
        sa.text(
            "ALTER TABLE pmwb_operation_issue MODIFY COLUMN issue_type "
            "ENUM('bug','data_abnormal','topic_analysis','spot_event','temp_task','other') "
            "NULL DEFAULT 'other' COMMENT '问题子类(细分类型)'"
        )
    )
    # 3) 责任人扩长以支持多选(逗号分隔)
    bind.execute(
        sa.text(
            "ALTER TABLE pmwb_operation_issue MODIFY COLUMN handler "
            "VARCHAR(512) NULL COMMENT '处理人(多选,逗号分隔)'"
        )
    )
    # 4) 影响范围 改名为 情况说明
    bind.execute(
        sa.text(
            "ALTER TABLE pmwb_operation_issue CHANGE COLUMN impact_scope situation_desc "
            "TEXT NULL COMMENT '情况说明'"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    # 逆向映射（topic_analysis/spot_event/temp_task 无对应旧值，归并 other；bug 反向为 system_failure）
    bind.execute(
        sa.text(
            """
            UPDATE pmwb_operation_issue SET issue_type = CASE issue_type
                WHEN 'data_abnormal' THEN 'data_error'
                WHEN 'bug' THEN 'system_failure'
                WHEN 'topic_analysis' THEN 'other'
                WHEN 'spot_event' THEN 'other'
                WHEN 'temp_task' THEN 'other'
                ELSE 'other' END
            """
        )
    )
    bind.execute(
        sa.text(
            "ALTER TABLE pmwb_operation_issue MODIFY COLUMN issue_type "
            "ENUM('data_error','system_failure','complaint','process_block','performance','other') "
            "NULL DEFAULT 'other' COMMENT '问题类型'"
        )
    )
    bind.execute(
        sa.text(
            "ALTER TABLE pmwb_operation_issue MODIFY COLUMN handler "
            "VARCHAR(64) NULL COMMENT '处理人'"
        )
    )
    bind.execute(
        sa.text(
            "ALTER TABLE pmwb_operation_issue CHANGE COLUMN situation_desc impact_scope "
            "TEXT NULL COMMENT '影响范围'"
        )
    )
