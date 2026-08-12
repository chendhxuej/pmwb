"""大模型提供方注册表 + 报告生成来源记录

Revision ID: 20260809000003
Revises: 20260809000002
"""
from alembic import op
import sqlalchemy as sa


revision = '20260809000003'
down_revision = '20260809000002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'pmwb_llm_provider',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False, comment='显示名称'),
        sa.Column('provider_type', sa.String(length=32), nullable=False, server_default='openai', comment='类型'),
        sa.Column('base_url', sa.String(length=512), nullable=False, comment='API Base URL'),
        sa.Column('model', sa.String(length=128), nullable=False, comment='模型名'),
        sa.Column('api_key', sa.Text(), nullable=True, comment='API Key（混淆存储）'),
        sa.Column('temperature', sa.Float(), nullable=True, comment='采样温度'),
        sa.Column('max_tokens', sa.Integer(), nullable=True, comment='单次最大 token'),
        sa.Column('timeout', sa.Integer(), nullable=True, comment='请求超时(秒)'),
        sa.Column('is_enabled', sa.Integer(), nullable=True, server_default='1', comment='是否启用'),
        sa.Column('is_default', sa.Integer(), nullable=True, server_default='0', comment='是否主用'),
        sa.Column('priority', sa.Integer(), nullable=True, server_default='0', comment='fallback 优先级'),
        sa.Column('last_error', sa.Text(), nullable=True, comment='最近连通性探测错误'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_llm_provider_default', 'is_default'),
        mysql_charset='utf8mb4',
        comment='底层大模型提供方注册表',
    )
    # 报告记录生成来源，便于「大模型不可用」反馈持久化
    op.add_column('pmwb_work_report',
                  sa.Column('gen_used_llm', sa.Integer(), nullable=True, server_default='0',
                            comment='是否由大模型生成(0/1)'))
    op.add_column('pmwb_work_report',
                  sa.Column('gen_model', sa.String(length=255), nullable=True,
                            comment='生成所用模型/提供方名'))
    op.add_column('pmwb_work_report',
                  sa.Column('gen_notice', sa.Text(), nullable=True,
                            comment='生成说明（如不可用原因）'))


def downgrade():
    op.drop_column('pmwb_work_report', 'gen_notice')
    op.drop_column('pmwb_work_report', 'gen_model')
    op.drop_column('pmwb_work_report', 'gen_used_llm')
    op.drop_table('pmwb_llm_provider')
