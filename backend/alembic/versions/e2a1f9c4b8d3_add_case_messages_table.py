"""add case messages table

Revision ID: e2a1f9c4b8d3
Revises: 4126c7be12e2
Create Date: 2026-04-26 16:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e2a1f9c4b8d3"
down_revision: Union[str, Sequence[str], None] = "4126c7be12e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "case_messages",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_case_messages_case_id", "case_messages", ["case_id"], unique=False)
    op.create_index("ix_case_messages_sent_at", "case_messages", ["sent_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_case_messages_sent_at", table_name="case_messages")
    op.drop_index("ix_case_messages_case_id", table_name="case_messages")
    op.drop_table("case_messages")
