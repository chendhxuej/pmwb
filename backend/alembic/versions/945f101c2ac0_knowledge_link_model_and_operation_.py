"""kc2_knowledge_link_operation_requirement_fields

Revision ID: 945f101c2ac0
Revises: 20260805000003
Create Date: 2026-08-08 12:25:15.419163

NOTE: 此迁移为 kc-2 知识关联重构的「增量加列」版本。
pmwb_knowledge_link 表已由更早的迁移 / create_all 建立（表中已存在），
pmwb_work_report 表必须保留（AI总结模块），
各业务表的 *_staff_id 冗余列保留（不在 kc-2 范围，避免误删生产数据）。
本迁移只补齐 kc-2 真正新增的两处字段。

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '945f101c2ac0'
down_revision: Union[str, None] = '20260805000003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'pmwb_operation_issue',
        sa.Column('root_cause_type', sa.String(length=64), nullable=True,
                  comment='根因分类：system_config/business_rule/data_issue/process_gap/external_dependency/other'),
    )
    op.add_column(
        'pmwb_operation_issue',
        sa.Column('impact_scope', sa.String(length=64), nullable=True,
                  comment='影响范围：single_customer/partial_region/full_region/business_line/platform'),
    )
    op.add_column(
        'pmwb_operation_issue',
        sa.Column('solution_type', sa.String(length=64), nullable=True,
                  comment='解决方案类型：config_fix/code_fix/data_repair/process_optimization/training/escalation/other'),
    )
    op.add_column(
        'pmwb_operation_issue',
        sa.Column('lesson_learned', sa.Text(), nullable=True,
                  comment='经验总结/防止复发措施'),
    )
    op.add_column(
        'pmwb_requirement_ext',
        sa.Column('manual_archived', sa.Integer(), nullable=True,
                  comment='操作手册是否已归档到业务知识'),
    )
    op.add_column(
        'pmwb_requirement_ext',
        sa.Column('manual_obsidian_path', sa.String(length=512), nullable=True,
                  comment='已归档操作手册的 Obsidian 路径'),
    )


def downgrade() -> None:
    op.drop_column('pmwb_requirement_ext', 'manual_obsidian_path')
    op.drop_column('pmwb_requirement_ext', 'manual_archived')
    op.drop_column('pmwb_operation_issue', 'lesson_learned')
    op.drop_column('pmwb_operation_issue', 'solution_type')
    op.drop_column('pmwb_operation_issue', 'impact_scope')
    op.drop_column('pmwb_operation_issue', 'root_cause_type')
