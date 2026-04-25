"""Add district to hospital

Revision ID: 4126c7be12e2
Revises: a73a4d1aafee
Create Date: 2026-04-23 17:46:30.336403

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4126c7be12e2'
down_revision: Union[str, Sequence[str], None] = 'a73a4d1aafee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op: baseline revision already includes this schema."""
    pass


def downgrade() -> None:
    """No-op: schema is managed by the baseline revision."""
    pass
