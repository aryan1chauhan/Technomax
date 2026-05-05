"""add fcm_token to users

Revision ID: 239e9004379f
Revises: 64384652098e
Create Date: 2026-04-01 07:01:59.785612

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '239e9004379f'
down_revision: Union[str, Sequence[str], None] = '64384652098e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op: baseline revision already includes this schema."""
    pass


def downgrade() -> None:
    """No-op: schema is managed by the baseline revision."""
    pass
