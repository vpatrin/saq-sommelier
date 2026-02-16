from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, Numeric, String, Text

from core.db.base import Base


class Product(Base):
    """SAQ product model - maps to ProductData from parser.

    Primary key: sku (SAQ product identifier, immutable)
    All fields nullable: SAQ pages have incomplete data (out-of-stock, minimal products)

    Fields are grouped by source:
    - JSON-LD fields (price, availability, rating, image)
    - HTML attribute fields (region, grape, alcohol, sugar)
    """

    __tablename__ = "products"
    __table_args__ = (
        # GIN trigram: substring search (WHERE name ILIKE '%margaux%')
        Index(
            "ix_products_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )

    # Primary key: SAQ SKU (immutable business identifier)
    sku = Column(String, primary_key=True, nullable=False, comment="SAQ product SKU")

    # Metadata
    url = Column(String, nullable=True, comment="SAQ product page URL")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
        comment="When first scraped",
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        comment="When last updated",
    )
    delisted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When removed from SAQ sitemap (NULL = active)",
    )

    # JSON-LD fields (from <script type="application/ld+json">)
    name = Column(String, nullable=True, index=True, comment="Product name")
    description = Column(Text, nullable=True, comment="Product description")
    category = Column(String, nullable=True, index=True, comment="Product category")
    country = Column(String, nullable=True, index=True, comment="Country of origin")
    barcode = Column(String, nullable=True, comment="GTIN-12 barcode")
    color = Column(String, nullable=True, comment="Wine color (red/white/rosé)")
    size = Column(String, nullable=True, comment="Bottle size (e.g., 750ml)")
    image = Column(String, nullable=True, comment="Product image URL")
    price = Column(Numeric(10, 2), nullable=True, index=True, comment="Price in CAD")
    currency = Column(String, nullable=True, comment="Currency code (CAD)")
    availability = Column(Boolean, nullable=True, comment="In stock?")
    manufacturer = Column(String, nullable=True, comment="Manufacturer name")
    rating = Column(Float, nullable=True, comment="Aggregate rating (0-5)")
    review_count = Column(Integer, nullable=True, comment="Number of reviews")

    # HTML attribute fields (from <ul class="list-attributs">)
    region = Column(String, nullable=True, index=True, comment="Wine region")
    appellation = Column(String, nullable=True, comment="Appellation d'origine")
    designation = Column(String, nullable=True, comment="Désignation réglementée")
    classification = Column(String, nullable=True, comment="Wine classification")
    grape = Column(String, nullable=True, comment="Grape variety (cépage)")
    alcohol = Column(String, nullable=True, comment="Alcohol content (e.g., 13.5%)")
    sugar = Column(String, nullable=True, comment="Sugar content")
    producer = Column(String, nullable=True, comment="Producer name")
    saq_code = Column(String, nullable=True, comment="Code SAQ (internal)")
    cup_code = Column(String, nullable=True, comment="Code CUP (UPC)")

    def __repr__(self) -> str:
        return f"<Product(sku={self.sku!r}, name={self.name!r})>"
