"""add gen meta to pmwb_user_story

记录用户故事的生成元信息（策略/命中模型/生成时间/AI 降级原因），
用于追溯「这批故事是谁生成的」并暴露 AI 静默降级。

Revision ID: a7c3e91d4b28
Revises: 602e92df6cb9
Create Date: 2026-09-07 19:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a7c3e91d4b28'
down_revision: Union[str, None] = '602e92df6cb9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'pmwb_user_story',
        sa.Column(
            'gen_strategy',
            sa.String(length=32),
            nullable=True,
            comment='生成策略: rules_v2/rules_v1/llm/rules_v2_fallback',
        ),
    )
    op.add_column(
        'pmwb_user_story',
        sa.Column('gen_provider', sa.String(length=128), nullable=True, comment='生成命中的大模型名称'),
    )
    op.add_column(
        'pmwb_user_story',
        sa.Column('gen_model', sa.String(length=128), nullable=True, comment='生成命中的模型标识'),
    )
    op.add_column(
        'pmwb_user_story',
        sa.Column('gen_at', sa.DateTime(), nullable=True, comment='生成时间'),
    )
    op.add_column(
        'pmwb_user_story',
        sa.Column('gen_fallback_reason', sa.Text(), nullable=True, comment='AI降级原因(仅降级时有值)'),
    )


def downgrade() -> None:
    op.drop_column('pmwb_user_story', 'gen_fallback_reason')
    op.drop_column('pmwb_user_story', 'gen_at')
    op.drop_column('pmwb_user_story', 'gen_model')
    op.drop_column('pmwb_user_story', 'gen_provider')
    op.drop_column('pmwb_user_story', 'gen_strategy')
