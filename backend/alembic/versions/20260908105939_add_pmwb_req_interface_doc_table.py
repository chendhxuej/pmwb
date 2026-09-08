"""add pmwb_req_interface_doc table

Revision ID: %(rev)s
Revises: 
Create Date: 2026-09-08
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '%(rev)s'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pmwb_req_interface_doc',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, comment='自增ID'),
        sa.Column('req_id', sa.String(length=64), nullable=False, comment='需求编号'),
        sa.Column('system_name', sa.String(length=255), nullable=False, comment='所属系统'),
        sa.Column('file_name', sa.String(length=500), comment='原始文件名'),
        sa.Column('local_path', sa.String(length=1024), comment='相对 vault 的文件路径'),
        sa.Column('obsidian_path', sa.String(length=512), comment='归档到业务知识后的 Obsidian 路径'),
        sa.Column('note', sa.String(length=500), comment='备注'),
        sa.Column('uploaded_by', sa.String(length=64), comment='上传人'),
        sa.Column('archived_at', sa.DateTime(), comment='归档到业务知识时间'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), comment='更新时间'),
        sa.UniqueConstraint('req_id', 'system_name', name='uk_req_interface_doc_system'),
        sa.Index('idx_req_interface_doc_req_id', 'req_id'),
        comment='需求接口规范文档（按系统）',
    )


def downgrade() -> None:
    op.drop_table('pmwb_req_interface_doc')
