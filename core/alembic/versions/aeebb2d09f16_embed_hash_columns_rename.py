"""embed hash columns rename

Revision ID: aeebb2d09f16
Revises: 203969d8fd14
Create Date: 2026-03-07 14:54:49.057442

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aeebb2d09f16"
down_revision: str | Sequence[str] | None = "203969d8fd14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("products", "attribute_hash", new_column_name="embedding_input_hash")
    op.alter_column("products", "embedded_hash", new_column_name="last_embedded_hash")


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("products", "embedding_input_hash", new_column_name="attribute_hash")
    op.alter_column("products", "last_embedded_hash", new_column_name="embedded_hash")
