"""Make requirement evaluation an editable list + widen priority

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-14 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) pmwb_requirement_evaluation 改造为可自由增删改的清单
    op.alter_column(
        'pmwb_requirement_evaluation', 'sent_email_id',
        existing_type=sa.Integer(),
        nullable=True,
        existing_nullable=False,
    )
    op.add_column('pmwb_requirement_evaluation', sa.Column('req_name', sa.String(length=255), nullable=True, comment='需求名称（冗余）'))
    op.add_column('pmwb_requirement_evaluation', sa.Column('proposer', sa.String(length=64), nullable=True, comment='提出人（冗余）'))
    op.add_column('pmwb_requirement_evaluation', sa.Column('send_datetime', sa.String(length=255), nullable=True, comment='邮件发送时间（溯源）'))
    op.add_column('pmwb_requirement_evaluation', sa.Column('sa_name', sa.String(length=64), nullable=True, comment='评估SA/团队负责人'))
    op.add_column('pmwb_requirement_evaluation', sa.Column('system_name', sa.String(length=255), nullable=True, comment='负责系统'))
    op.add_column('pmwb_requirement_evaluation', sa.Column('review_workload', sa.Numeric(precision=10, scale=2), nullable=True, comment='复核工作量(人天)'))

    # 2) pmwb_requirement_ext.priority 由固定枚举改为自由字符串，支持新增枚举值
    op.alter_column(
        'pmwb_requirement_ext', 'priority',
        existing_type=sa.Enum('P0', 'P1', 'P2', 'P3'),
        type_=sa.String(length=64),
        existing_nullable=True,
    )
    # 3) pmwb_requirement_ext 增加 eval_seeded 标记，避免删除后重新播种复活
    op.add_column('pmwb_requirement_ext', sa.Column('eval_seeded', sa.Integer(), nullable=True, comment='团队评估是否已从 sent_emails 播种'))

    # 4) 历史数据一次性播种：把已存在的 sent_emails 评估直接写入可编辑评估表
    # （运行时首次访问也会按需播种，此处仅为离线保证一致性，可重复执行）
    from sqlalchemy import text as _sa_text
    op.execute(_sa_text("""
        INSERT INTO pmwb_requirement_evaluation
            (sent_email_id, req_id, req_name, proposer, send_datetime, sa_name, system_name, workload, review_workload, opinion, dev_ticket_no, created_at, updated_at)
        SELECT s.id, s.req_id, s.req_name, s.proposer, s.send_datetime, s.sa_name, s.system_name,
               s.workload, NULL, '', s.dev_ticket_no, NOW(), NOW()
        FROM sent_emails s
        WHERE NOT EXISTS (
            SELECT 1 FROM pmwb_requirement_evaluation e WHERE e.sent_email_id = s.id
        )
    """))
    op.execute(_sa_text("""
        UPDATE pmwb_requirement_ext SET eval_seeded = 1
        WHERE req_id IN (SELECT DISTINCT req_id FROM sent_emails)
    """))


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM pmwb_requirement_evaluation WHERE sent_email_id IS NOT NULL"))
    op.execute(sa.text("UPDATE pmwb_requirement_ext SET eval_seeded = 0"))
    op.alter_column(
        'pmwb_requirement_ext', 'priority',
        existing_type=sa.String(length=64),
        type_=sa.Enum('P0', 'P1', 'P2', 'P3'),
        existing_nullable=True,
    )
    op.drop_column('pmwb_requirement_evaluation', 'review_workload')
    op.drop_column('pmwb_requirement_evaluation', 'system_name')
    op.drop_column('pmwb_requirement_evaluation', 'sa_name')
    op.drop_column('pmwb_requirement_evaluation', 'send_datetime')
    op.drop_column('pmwb_requirement_evaluation', 'proposer')
    op.drop_column('pmwb_requirement_evaluation', 'req_name')
    op.alter_column(
        'pmwb_requirement_evaluation', 'sent_email_id',
        existing_type=sa.Integer(),
        nullable=False,
        existing_nullable=True,
    )
