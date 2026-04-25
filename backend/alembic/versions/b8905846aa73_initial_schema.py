"""initial schema

Revision ID: b8905846aa73
Revises:
Create Date: 2026-03-31 05:30:13.175587

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b8905846aa73"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the baseline schema to match the current SQLAlchemy models."""
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.String(), nullable=False),
        sa.Column("condition_type", sa.String(), nullable=True),
        sa.Column("severity_score", sa.Integer(), nullable=True),
        sa.Column("ambulance_lat", sa.Float(), nullable=True),
        sa.Column("ambulance_lng", sa.Float(), nullable=True),
        sa.Column("selected_hospital_id", sa.Integer(), nullable=True),
        sa.Column("selected_hospital_name", sa.String(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("score_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("vitals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("required_equipment", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("ambulance_equipment", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("all_hospitals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_case_id"), "audit_logs", ["case_id"], unique=False)

    op.create_table(
        "hospitals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("hospital_type", sa.String(length=20), server_default=sa.text("'both'"), nullable=False),
        sa.Column("has_icu", sa.Boolean(), server_default=sa.text("'false'"), nullable=False),
        sa.Column("specialists", sa.JSON(), nullable=True),
        sa.Column("district", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_hospitals_district"), "hospitals", ["district"], unique=False)
    op.create_index(op.f("ix_hospitals_id"), "hospitals", ["id"], unique=False)
    op.create_index(op.f("ix_hospitals_name"), "hospitals", ["name"], unique=False)

    op.create_table(
        "availabilities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hospital_id", sa.Integer(), nullable=True),
        sa.Column("beds", sa.Integer(), nullable=True),
        sa.Column("icu", sa.Integer(), nullable=True),
        sa.Column("doctors", sa.Integer(), nullable=True),
        sa.Column("equipment", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("accepting", sa.Boolean(), nullable=True),
        sa.Column("specialists", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_availabilities_id"), "availabilities", ["id"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("password_hash", sa.String(), nullable=True),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("hospital_id", sa.Integer(), nullable=True),
        sa.Column("fcm_token", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "cases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("condition", sa.String(), nullable=True),
        sa.Column("custom_condition", sa.String(), nullable=True),
        sa.Column("equipment_needed", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("ambulance_lat", sa.Float(), nullable=True),
        sa.Column("ambulance_lng", sa.Float(), nullable=True),
        sa.Column("assigned_hospital_id", sa.Integer(), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("eta_minutes", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["assigned_hospital_id"], ["hospitals.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cases_id"), "cases", ["id"], unique=False)

    op.create_table(
        "case_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_role", sa.String(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actual_eta_minutes", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_case_events_id"), "case_events", ["id"], unique=False)

    op.create_table(
        "decision_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("hospital_id", sa.Integer(), nullable=False),
        sa.Column("rank_position", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("eta_minutes", sa.Float(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("available_beds_snapshot", sa.Integer(), nullable=False),
        sa.Column("icu_beds_snapshot", sa.Integer(), nullable=False),
        sa.Column("is_selected", sa.Boolean(), nullable=False),
        sa.Column("score_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_decision_candidates_case_id"), "decision_candidates", ["case_id"], unique=False)
    op.create_index(op.f("ix_decision_candidates_hospital_id"), "decision_candidates", ["hospital_id"], unique=False)
    op.create_index(op.f("ix_decision_candidates_id"), "decision_candidates", ["id"], unique=False)

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("target", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("is_dlq", sa.Boolean(), nullable=False),
        sa.Column("fallback_from_id", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
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

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("target_url", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("signature", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_webhook_deliveries_case_id"), "webhook_deliveries", ["case_id"], unique=False)
    op.create_index(op.f("ix_webhook_deliveries_event_type"), "webhook_deliveries", ["event_type"], unique=False)
    op.create_index(op.f("ix_webhook_deliveries_id"), "webhook_deliveries", ["id"], unique=False)
    op.create_index(op.f("ix_webhook_deliveries_status"), "webhook_deliveries", ["status"], unique=False)


def downgrade() -> None:
    """Drop the baseline schema."""
    op.drop_index(op.f("ix_webhook_deliveries_status"), table_name="webhook_deliveries")
    op.drop_index(op.f("ix_webhook_deliveries_id"), table_name="webhook_deliveries")
    op.drop_index(op.f("ix_webhook_deliveries_event_type"), table_name="webhook_deliveries")
    op.drop_index(op.f("ix_webhook_deliveries_case_id"), table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")

    op.drop_index(op.f("ix_notification_deliveries_user_id"), table_name="notification_deliveries")
    op.drop_index(op.f("ix_notification_deliveries_status"), table_name="notification_deliveries")
    op.drop_index(op.f("ix_notification_deliveries_provider"), table_name="notification_deliveries")
    op.drop_index(op.f("ix_notification_deliveries_id"), table_name="notification_deliveries")
    op.drop_index(op.f("ix_notification_deliveries_channel"), table_name="notification_deliveries")
    op.drop_index(op.f("ix_notification_deliveries_case_id"), table_name="notification_deliveries")
    op.drop_table("notification_deliveries")

    op.drop_index(op.f("ix_decision_candidates_id"), table_name="decision_candidates")
    op.drop_index(op.f("ix_decision_candidates_hospital_id"), table_name="decision_candidates")
    op.drop_index(op.f("ix_decision_candidates_case_id"), table_name="decision_candidates")
    op.drop_table("decision_candidates")

    op.drop_index(op.f("ix_case_events_id"), table_name="case_events")
    op.drop_table("case_events")

    op.drop_index(op.f("ix_cases_id"), table_name="cases")
    op.drop_table("cases")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_table("users")

    op.drop_index(op.f("ix_availabilities_id"), table_name="availabilities")
    op.drop_table("availabilities")

    op.drop_index(op.f("ix_hospitals_name"), table_name="hospitals")
    op.drop_index(op.f("ix_hospitals_id"), table_name="hospitals")
    op.drop_index(op.f("ix_hospitals_district"), table_name="hospitals")
    op.drop_table("hospitals")

    op.drop_index(op.f("ix_audit_logs_case_id"), table_name="audit_logs")
    op.drop_table("audit_logs")
