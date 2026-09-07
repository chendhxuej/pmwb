"""add pmwb_material and pmwb_material_category tables

业务资料库：统一材料索引表 + 两级可增删分类树。
只登记指针、不搬迁物理文件（storage_root + rel_path 还原绝对路径）。

注意：本迁移已手工剔除 autogenerate 误报的历史表漂移（comment / staff_id 列等），
仅保留两张新表的建表与删表语句。

Revision ID: 602e92df6cb9
Revises: bf9d37f54af3
Create Date: 2026-09-03 21:44:24.876598

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '602e92df6cb9'
down_revision: Union[str, None] = 'bf9d37f54af3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pmwb_material_category',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='自增ID'),
        sa.Column('code', sa.String(length=64), nullable=False, comment='分类编码，全局唯一'),
        sa.Column('name', sa.String(length=128), nullable=False, comment='分类名称'),
        sa.Column('parent_id', sa.Integer(), nullable=True, comment='父分类ID，空表示一级分类'),
        sa.Column('sort_order', sa.Integer(), nullable=True, comment='排序号，越小越靠前'),
        sa.Column('enabled', sa.Boolean(), nullable=True, comment='是否启用，停用后不出现在下拉但保留历史归属'),
        sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
        sa.ForeignKeyConstraint(['parent_id'], ['pmwb_material_category.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
        comment='业务资料库材料分类树',
    )
    op.create_index('ix_mat_cat_parent', 'pmwb_material_category', ['parent_id'], unique=False)

    op.create_table(
        'pmwb_material',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='自增ID'),
        sa.Column('category_id', sa.Integer(), nullable=True, comment='所属分类ID'),
        sa.Column('domain_code', sa.String(length=64), nullable=True, comment='业务领域编码，复用 pmwb_business_domain'),
        sa.Column('source_type', sa.String(length=64), nullable=False,
                  comment='来源类型: operation_issue/research_issue/requirement/dev_deliverable/keywork_deliverable/req_manual/manual_upload'),
        sa.Column('source_id', sa.String(length=255), nullable=True, comment='来源业务对象ID（运营工单id / req_id / 重点工作id）'),
        sa.Column('source_no', sa.String(length=128), nullable=True, comment='冗余来源单号（issue_no / req_id），供搜索与展示'),
        sa.Column('source_title', sa.String(length=500), nullable=True, comment='冗余来源标题，避免列表页N次联表'),
        sa.Column('file_name', sa.String(length=500), nullable=False, comment='原始文件名（展示与搜索用）'),
        sa.Column('stored_name', sa.String(length=500), nullable=False, comment='落盘文件名（UUID前缀防覆盖）'),
        sa.Column('storage_root', sa.String(length=16), nullable=True, comment='存储根: uploads / vault'),
        sa.Column('rel_path', sa.String(length=1024), nullable=False, comment='相对 storage_root 的路径'),
        sa.Column('rel_path_hash', sa.String(length=64), nullable=False,
                  comment='rel_path 的 sha256 十六进制，用于唯一约束（MySQL utf8mb4 索引 3072 字节限制）'),
        sa.Column('file_size', sa.Integer(), nullable=True, comment='文件大小(字节)'),
        sa.Column('file_ext', sa.String(length=32), nullable=True, comment='扩展名小写，如 xlsx'),
        sa.Column('file_type', sa.String(length=128), nullable=True, comment='MIME 类型'),
        sa.Column('origin', sa.String(length=32), nullable=True, comment='来源方式: manual 手工上传 / auto 汇聚登记'),
        sa.Column('uploaded_by', sa.String(length=64), nullable=True, comment='上传人'),
        sa.Column('note', sa.Text(), nullable=True, comment='备注，参与模糊搜索'),
        sa.Column('tags', sa.String(length=512), nullable=True, comment='标签，逗号分隔'),
        sa.Column('download_count', sa.Integer(), nullable=True, comment='下载次数'),
        sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
        sa.ForeignKeyConstraint(['category_id'], ['pmwb_material_category.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_type', 'source_id', 'rel_path_hash', name='uk_mat_dedup'),
        comment='业务资料库统一材料索引表',
    )
    op.create_index('idx_mat_source', 'pmwb_material', ['source_type', 'source_id'], unique=False)
    op.create_index('idx_mat_category', 'pmwb_material', ['category_id'], unique=False)
    op.create_index('idx_mat_domain', 'pmwb_material', ['domain_code'], unique=False)
    op.create_index('idx_mat_ext', 'pmwb_material', ['file_ext'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_mat_ext', table_name='pmwb_material')
    op.drop_index('idx_mat_domain', table_name='pmwb_material')
    op.drop_index('idx_mat_category', table_name='pmwb_material')
    op.drop_index('idx_mat_source', table_name='pmwb_material')
    op.drop_table('pmwb_material')
    op.drop_index('ix_mat_cat_parent', table_name='pmwb_material_category')
    op.drop_table('pmwb_material_category')
