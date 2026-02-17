"""initial schema

Revision ID: b5c67feb72f8
Revises:
Create Date: 2026-02-17 13:50:04.143147

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5c67feb72f8"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "products",
        sa.Column("sku", sa.String(), nullable=False, comment="SAQ product SKU"),
        sa.Column("url", sa.String(), nullable=True, comment="SAQ product page URL"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When first scraped",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When last updated",
        ),
        sa.Column(
            "delisted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When removed from SAQ sitemap (NULL = active)",
        ),
        sa.Column("name", sa.String(), nullable=True, comment="Product name"),
        sa.Column("description", sa.Text(), nullable=True, comment="Product description"),
        sa.Column("category", sa.String(), nullable=True, comment="Product category"),
        sa.Column("country", sa.String(), nullable=True, comment="Country of origin"),
        sa.Column("barcode", sa.String(), nullable=True, comment="GTIN-12 barcode"),
        sa.Column("color", sa.String(), nullable=True, comment="Wine color (red/white/rosé)"),
        sa.Column("size", sa.String(), nullable=True, comment="Bottle size (e.g., 750ml)"),
        sa.Column("image", sa.String(), nullable=True, comment="Product image URL"),
        sa.Column(
            "price", sa.Numeric(precision=10, scale=2), nullable=True, comment="Price in CAD"
        ),
        sa.Column("currency", sa.String(), nullable=True, comment="Currency code (CAD)"),
        sa.Column("availability", sa.Boolean(), nullable=True, comment="In stock?"),
        sa.Column("rating", sa.Float(), nullable=True, comment="Aggregate rating (0-5)"),
        sa.Column("review_count", sa.Integer(), nullable=True, comment="Number of reviews"),
        sa.Column("region", sa.String(), nullable=True, comment="Wine region"),
        sa.Column("appellation", sa.String(), nullable=True, comment="Appellation d'origine"),
        sa.Column("designation", sa.String(), nullable=True, comment="Désignation réglementée"),
        sa.Column("classification", sa.String(), nullable=True, comment="Wine classification"),
        sa.Column("grape", sa.String(), nullable=True, comment="Grape variety (cépage)"),
        sa.Column("alcohol", sa.String(), nullable=True, comment="Alcohol content (e.g., 13.5%)"),
        sa.Column("sugar", sa.String(), nullable=True, comment="Sugar content"),
        sa.Column("producer", sa.String(), nullable=True, comment="Producer name"),
        sa.Column("saq_code", sa.String(), nullable=True, comment="Code SAQ (internal)"),
        sa.Column("cup_code", sa.String(), nullable=True, comment="Code CUP (UPC)"),
        sa.PrimaryKeyConstraint("sku"),
    )
    op.create_index(op.f("ix_products_category"), "products", ["category"], unique=False)
    op.create_index(op.f("ix_products_country"), "products", ["country"], unique=False)
    op.create_index(op.f("ix_products_created_at"), "products", ["created_at"], unique=False)
    op.create_index(op.f("ix_products_name"), "products", ["name"], unique=False)
    op.create_index(
        "ix_products_name_trgm",
        "products",
        ["name"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.create_index(op.f("ix_products_price"), "products", ["price"], unique=False)
    op.create_index(op.f("ix_products_region"), "products", ["region"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_products_region"), table_name="products")
    op.drop_index(op.f("ix_products_price"), table_name="products")
    op.drop_index(
        "ix_products_name_trgm",
        table_name="products",
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.drop_index(op.f("ix_products_name"), table_name="products")
    op.drop_index(op.f("ix_products_created_at"), table_name="products")
    op.drop_index(op.f("ix_products_country"), table_name="products")
    op.drop_index(op.f("ix_products_category"), table_name="products")
    op.drop_table("products")
