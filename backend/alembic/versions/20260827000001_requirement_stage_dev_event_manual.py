"""requirement stage log / dev event / manual tables

Revision ID: 20260827000001
Revises: 04173c6a8050, 20260825000001
Create Date: 2026-08-27 14:30:00

需求与交付模块增强：
1. pmwb_requirement_stage_log 需求环节状态时间日志（6 环节进入/完成时间）
2. pmwb_req_dev_event 开发事件记录（启动开发环节）
3. pmwb_req_manual 操作手册（生产部署环节，按系统区分）

本迁移同时收敛 alembic 双 head（04173c6a8050 与 20260825000001）。
幂等设计：建表前先检查表是否已存在（Base.metadata.create_all 可能已建）。
"""
from alembic import op
import sqlalchemy as sa

revision = "20260827000001"
down_revision = ("04173c6a8050", "20260825000001")
branch_labels = None
depends_on = None

_TABLES = {
    "pmwb_requirement_stage_log": """
        CREATE TABLE pmwb_requirement_stage_log (
            id INTEGER NOT NULL AUTO_INCREMENT,
            req_id VARCHAR(64) NOT NULL COMMENT '需求编号，对应 sent_emails.req_id',
            stage VARCHAR(32) NOT NULL COMMENT '环节: collect/evaluate/story/doc/dev/deploy',
            entered_at DATETIME COMMENT '进入时间',
            left_at DATETIME COMMENT '完成/离开时间（下一环节进入时间）',
            source VARCHAR(16) COMMENT '时间来源: auto/manual/backfill',
            created_at DATETIME COMMENT '创建时间',
            updated_at DATETIME COMMENT '更新时间',
            PRIMARY KEY (id),
            UNIQUE KEY uk_req_stage (req_id, stage),
            KEY idx_req_stage_req_id (req_id)
        ) COMMENT '需求环节状态时间日志'
    """,
    "pmwb_req_dev_event": """
        CREATE TABLE pmwb_req_dev_event (
            id INTEGER NOT NULL AUTO_INCREMENT,
            req_id VARCHAR(64) NOT NULL COMMENT '需求编号',
            event_time DATETIME COMMENT '事件发生时间',
            event_type VARCHAR(32) COMMENT '事件类型: dev_start/joint_test/test/bugfix/release_ready/other',
            title VARCHAR(255) COMMENT '事件标题',
            content TEXT COMMENT '事件详情',
            created_at DATETIME COMMENT '创建时间',
            updated_at DATETIME COMMENT '更新时间',
            PRIMARY KEY (id),
            KEY idx_dev_event_req_id (req_id)
        ) COMMENT '需求开发事件记录'
    """,
    "pmwb_req_manual": """
        CREATE TABLE pmwb_req_manual (
            id INTEGER NOT NULL AUTO_INCREMENT,
            req_id VARCHAR(64) NOT NULL COMMENT '需求编号',
            system_name VARCHAR(255) NOT NULL COMMENT '所属系统（来自团队评估，一系统一份手册）',
            file_name VARCHAR(500) COMMENT '原始文件名',
            local_path VARCHAR(1024) COMMENT '相对 vault 的文件路径',
            obsidian_path VARCHAR(512) COMMENT '归档到业务知识后的 Obsidian 路径',
            note VARCHAR(500) COMMENT '备注',
            uploaded_by VARCHAR(64) COMMENT '上传人',
            archived_at DATETIME COMMENT '归档到业务知识时间',
            created_at DATETIME COMMENT '创建时间',
            updated_at DATETIME COMMENT '更新时间',
            PRIMARY KEY (id),
            UNIQUE KEY uk_req_manual_system (req_id, system_name),
            KEY idx_req_manual_req_id (req_id)
        ) COMMENT '需求操作手册（按系统）'
    """,
}


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        sa.text("SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = :n"),
        {"n": name},
    ).fetchone()
    return bool(row and row[0])


def upgrade():
    conn = op.get_bind()
    for name, ddl in _TABLES.items():
        if not _table_exists(conn, name):
            conn.execute(sa.text(ddl))


def downgrade():
    conn = op.get_bind()
    for name in _TABLES:
        if _table_exists(conn, name):
            conn.execute(sa.text(f"DROP TABLE {name}"))
