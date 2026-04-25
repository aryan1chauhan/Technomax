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
    op.create_table(
        "decision_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("hospital_id", sa.Integer(), nullable=False),
        sa.Column("rank_position", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("eta_minutes", sa.Float(), nullable=False, server_default="0"),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("available_beds_snapshot", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("icu_beds_snapshot", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_selected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("score_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_decision_candidates_id"), "decision_candidates", ["id"], unique=False)
    op.create_index(op.f("ix_decision_candidates_case_id"), "decision_candidates", ["case_id"], unique=False)
    op.create_index(op.f("ix_decision_candidates_hospital_id"), "decision_candidates", ["hospital_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_decision_candidates_hospital_id"), table_name="decision_candidates")
    op.drop_index(op.f("ix_decision_candidates_case_id"), table_name="decision_candidates")
    op.drop_index(op.f("ix_decision_candidates_id"), table_name="decision_candidates")
    op.drop_table("decision_candidates")
