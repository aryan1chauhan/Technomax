"""add hospital_type and has_icu to hospitals

Revision ID: 8f3b4b5d9c21
Revises: 239e9004379f
Create Date: 2026-04-09 12:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f3b4b5d9c21"
down_revision: Union[str, Sequence[str], None] = "239e9004379f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op: baseline revision already includes this schema."""
    pass


def downgrade() -> None:
    """No-op: schema is managed by the baseline revision."""
    pass
