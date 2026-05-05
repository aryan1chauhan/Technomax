"""add webhook_deliveries table

Revision ID: f7a1c2d4e5b6
Revises: d3c9f4a12e01
Create Date: 2026-04-19 09:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f7a1c2d4e5b6"
down_revision: Union[str, Sequence[str], None] = "d3c9f4a12e01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op: baseline revision already includes this schema."""
    pass


def downgrade() -> None:
    """No-op: schema is managed by the baseline revision."""
    pass
