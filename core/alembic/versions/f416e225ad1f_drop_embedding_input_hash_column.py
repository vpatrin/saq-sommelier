"""drop embedding_input_hash column

Revision ID: f416e225ad1f
Revises: dc81b1df4586
Create Date: 2026-03-07 16:43:59.330886

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f416e225ad1f"
down_revision: str | Sequence[str] | None = "dc81b1df4586"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("products", "embedding_input_hash")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "products",
        sa.Column("embedding_input_hash", sa.VARCHAR(), nullable=True),
    )
