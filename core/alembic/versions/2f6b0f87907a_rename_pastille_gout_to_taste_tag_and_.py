"""rename pastille_gout to taste_tag and cepage_adobe to grape_blend

Revision ID: 2f6b0f87907a
Revises: a1665520b1d7
Create Date: 2026-03-07 12:23:57.845415

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2f6b0f87907a"
down_revision: str | Sequence[str] | None = "a1665520b1d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("products", "pastille_gout", new_column_name="taste_tag")
    op.alter_column("products", "cepage_adobe", new_column_name="grape_blend")


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("products", "taste_tag", new_column_name="pastille_gout")
    op.alter_column("products", "grape_blend", new_column_name="cepage_adobe")
