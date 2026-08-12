"""merge_meeting_action_and_user_story_rules

Revision ID: 6eb2861442a5
Revises: 20260722000001, 768014c30bda
Create Date: 2026-07-22 16:10:17.933588

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6eb2861442a5'
down_revision: Union[str, None] = ('20260722000001', '768014c30bda')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
