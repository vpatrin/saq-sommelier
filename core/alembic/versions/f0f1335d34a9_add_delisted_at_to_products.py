"""add delisted_at to products

Revision ID: f0f1335d34a9
Revises: 730b893703aa
Create Date: 2026-02-16 14:05:13.855943

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f0f1335d34a9"
down_revision: str | Sequence[str] | None = "730b893703aa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "products",
        sa.Column(
            "delisted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When removed from SAQ sitemap (NULL = active)",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("products", "delisted_at")
