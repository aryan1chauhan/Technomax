"""add case status and events

Revision ID: 64384652098e
Revises: b8905846aa73
Create Date: 2026-03-31 17:11:16.749751

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64384652098e'
down_revision: Union[str, Sequence[str], None] = 'b8905846aa73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op: baseline revision already includes this schema."""
    pass


def downgrade() -> None:
    """No-op: schema is managed by the baseline revision."""
    pass
