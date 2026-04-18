"""add audit_logs table

Revision ID: a1f3c9e72d04
Revises: 8f3b4b5d9c21
Create Date: 2026-04-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1f3c9e72d04'
down_revision: Union[str, Sequence[str], None] = '8f3b4b5d9c21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create audit_logs table (idempotent — safe if hand-created in prior session)."""
    # Use raw SQL so we can use IF NOT EXISTS — Alembic's create_table does not support it.
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id                     SERIAL PRIMARY KEY,
            case_id                TEXT        NOT NULL UNIQUE,
            condition_type         TEXT,
            severity_score         INTEGER,
            ambulance_lat          DOUBLE PRECISION,
            ambulance_lng          DOUBLE PRECISION,
            selected_hospital_id   INTEGER,
            selected_hospital_name TEXT,
            score                  DOUBLE PRECISION DEFAULT 0.0,
            score_breakdown        JSONB,
            vitals                 JSONB,
            required_equipment     TEXT[],
            ambulance_equipment    TEXT[],
            all_hospitals          JSONB,
            timestamp              TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)


    # Index on timestamp for the /metrics window queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_audit_logs_timestamp
        ON audit_logs (timestamp)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_logs")
