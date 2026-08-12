"""sent_emails.req_id 增加索引，加速按需求编号的高频查询。

高频查询路径：services/requirement.py 多次按 req_id 过滤 sent_emails，
此前无索引，全表扫描。单列索引非破坏，可逆。
"""
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260725000002"
down_revision: str = "20260725000001"
branch_labels: tuple = None
depends_on: tuple = None


def upgrade() -> None:
    op.create_index("ix_sent_emails_req_id", "sent_emails", ["req_id"])


def downgrade() -> None:
    op.drop_index("ix_sent_emails_req_id", table_name="sent_emails")
