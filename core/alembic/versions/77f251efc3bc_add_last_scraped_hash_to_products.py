"""add last_scraped_hash to products

Revision ID: 77f251efc3bc
Revises: f416e225ad1f
Create Date: 2026-03-08 20:07:06.499938

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "77f251efc3bc"
down_revision: str | Sequence[str] | None = "f416e225ad1f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "products",
        sa.Column(
            "last_scraped_hash",
            sa.String(),
            nullable=True,
            comment="SHA256 of scraped ProductData fields — skip write when unchanged",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("products", "last_scraped_hash")
