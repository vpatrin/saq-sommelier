"""drop invite_codes table

Revision ID: c2e04e28cb5f
Revises: 27ee92e478ce
Create Date: 2026-04-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2e04e28cb5f"
down_revision: str | Sequence[str] | None = "27ee92e478ce"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(op.f("ix_invite_codes_code"), table_name="invite_codes")
    op.drop_table("invite_codes")


def downgrade() -> None:
    op.create_table(
        "invite_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False, comment="Invite code string"),
        sa.Column(
            "created_by_id", sa.Integer(), nullable=False, comment="Admin who generated this code"
        ),
        sa.Column(
            "used_by_id",
            sa.Integer(),
            nullable=True,
            comment="User who redeemed this code (NULL = unused)",
        ),
        sa.Column(
            "used_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the code was redeemed",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When the code was generated",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["used_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_invite_codes_code"), "invite_codes", ["code"], unique=True)
