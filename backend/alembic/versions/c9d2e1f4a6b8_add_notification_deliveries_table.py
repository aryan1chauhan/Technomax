"""add notification_deliveries table

Revision ID: c9d2e1f4a6b8
Revises: f7a1c2d4e5b6
Create Date: 2026-04-19 09:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c9d2e1f4a6b8"
down_revision: Union[str, Sequence[str], None] = "f7a1c2d4e5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("target", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_dlq", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fallback_from_id", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["fallback_from_id"], ["notification_deliveries.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notification_deliveries_case_id"), "notification_deliveries", ["case_id"], unique=False)
    op.create_index(op.f("ix_notification_deliveries_channel"), "notification_deliveries", ["channel"], unique=False)
    op.create_index(op.f("ix_notification_deliveries_id"), "notification_deliveries", ["id"], unique=False)
    op.create_index(op.f("ix_notification_deliveries_provider"), "notification_deliveries", ["provider"], unique=False)
    op.create_index(op.f("ix_notification_deliveries_status"), "notification_deliveries", ["status"], unique=False)
    op.create_index(op.f("ix_notification_deliveries_user_id"), "notification_deliveries", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_deliveries_user_id"), table_name="notification_deliveries")
    op.drop_index(op.f("ix_notification_deliveries_status"), table_name="notification_deliveries")
    op.drop_index(op.f("ix_notification_deliveries_provider"), table_name="notification_deliveries")
    op.drop_index(op.f("ix_notification_deliveries_id"), table_name="notification_deliveries")
    op.drop_index(op.f("ix_notification_deliveries_channel"), table_name="notification_deliveries")
    op.drop_index(op.f("ix_notification_deliveries_case_id"), table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
