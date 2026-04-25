"""Add actual_eta_minutes to case_events

Revision ID: a73a4d1aafee
Revises: c9d2e1f4a6b8
Create Date: 2026-04-23 09:22:17.626184

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a73a4d1aafee'
down_revision: Union[str, Sequence[str], None] = 'c9d2e1f4a6b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op: baseline revision already includes this schema."""
    pass


def downgrade() -> None:
    """No-op: schema is managed by the baseline revision."""
    pass
