"""add decision_candidates table

Revision ID: d3c9f4a12e01
Revises: a1f3c9e72d04
Create Date: 2026-04-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d3c9f4a12e01"
down_revision: Union[str, Sequence[str], None] = "a1f3c9e72d04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create decision_candidates table if not exists."""
    # Table is already created in baseline, this is a no-op for existing databases
    pass


def downgrade() -> None:
    """Downgrade is a no-op."""
    pass
