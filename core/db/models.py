from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

from core.db.base import Base

# Embedding model — change both together if swapping models
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
EMBEDDING_MODEL_DIMENSIONS = 1024


class Store(Base):
    """SAQ physical store location.

    Populated automatically on first scraper run when the stores table is empty.
    Primary key is the SAQ store identifier (e.g. "23009"), stable across API versions.
    """

    __tablename__ = "stores"

    saq_store_id = Column(
        String, primary_key=True, comment="SAQ store identifier (API 'identifier' field)"
    )
    name = Column(String, nullable=False, comment="Store display name")
    store_type = Column(
        String, nullable=True, comment="SAQ, SAQ Sélection, SAQ Express, SAQ Dépôt, etc."
    )
    address = Column(String, nullable=True, comment="Street address (address1)")
    city = Column(String, nullable=False, index=True, comment="City")
    postcode = Column(String, nullable=True, comment="Postal code")
    telephone = Column(String, nullable=True, comment="Phone number")
    latitude = Column(Float, nullable=True, comment="GPS latitude")
    longitude = Column(Float, nullable=True, comment="GPS longitude")
    temporarily_closed = Column(
        Boolean, nullable=False, default=False, comment="Temporarily closed flag"
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="When first scraped",
    )

    def __repr__(self) -> str:
        return (
            f"<Store(saq_store_id={self.saq_store_id!r}, name={self.name!r}, city={self.city!r})>"
        )


class Product(Base):
    """SAQ product model - maps to ProductData from products.

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
        # GIN on store_availability for @> containment queries ("available at store X")
        Index(
            "ix_products_store_availability_gin",
            "store_availability",
            postgresql_using="gin",
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
    size = Column(String, nullable=True, comment="Bottle size (e.g., 750ml)")
    image = Column(String, nullable=True, comment="Product image URL")
    price = Column(Numeric(10, 2), nullable=True, index=True, comment="Price in CAD")
    online_availability = Column(Boolean, nullable=True, comment="Available online?")
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

    # Wine attributes (writer: --enrich-wines)
    taste_tag = Column(
        String, nullable=True, comment="SAQ taste profile (e.g. 'Aromatique et souple')"
    )
    vintage = Column(String, nullable=True, comment="Millésime (e.g. '2023')")
    tasting_profile = Column(JSONB, nullable=True, comment="portrait_* attributes from Adobe")
    grape_blend = Column(
        JSONB,
        nullable=True,
        comment='Structured blend: [{"code":"MALB","pct":96},{"code":"SYRA","pct":4}]',
    )

    # Availability (writer: --availability-check)
    store_availability = Column(
        JSONB,
        nullable=True,
        comment='Store IDs carrying this product: ["23002","23004",...]',
    )

    # Embedding support (writer: --embed-sync)
    embedding = Column(
        Vector(EMBEDDING_MODEL_DIMENSIONS),
        nullable=True,
        comment="Wine semantic embedding (multilingual-e5-large, 1024d)",
    )
    embedding_input_hash = Column(
        String, nullable=True, comment="Hash of embedding-relevant fields for change detection"
    )
    last_embedded_hash = Column(
        String,
        nullable=True,
        comment="embedding_input_hash at time of last --embed-sync run",
    )

    def __repr__(self) -> str:
        return f"<Product(sku={self.sku!r}, name={self.name!r})>"


class Watch(Base):
    """User watch on a product — triggers alerts on availability changes."""

    __tablename__ = "watches"

    # A given can watch SKU A and SKU B, but can't watch SKU A twice
    __table_args__ = (UniqueConstraint("user_id", "sku", name="uq_watches_user_sku"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Opaque string — the backend doesn't parse or validate it.
    # Channel prefix is the caller's responsibility (tg:, wa:, email:, etc.).
    user_id = Column(
        String,
        nullable=False,
        index=True,
        comment="Channel-prefixed user ID (e.g. tg:123456)",
    )
    sku = Column(
        String,
        ForeignKey("products.sku"),
        nullable=False,
        index=True,
        comment="Watched product SKU",
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="When watch was created",
    )

    def __repr__(self) -> str:
        return f"<Watch(user_id={self.user_id!r}, sku={self.sku!r})>"


class UserStorePreference(Base):
    """Per-user preferred SAQ store — used to scope in-store restock alerts."""

    __tablename__ = "user_store_preferences"

    # Opaque string — consistent with Watch.user_id convention.
    user_id = Column(
        String,
        primary_key=True,
        comment="Channel-prefixed user ID (e.g. tg:123456)",
    )
    saq_store_id = Column(
        String,
        ForeignKey("stores.saq_store_id"),
        primary_key=True,
        comment="Preferred store identifier",
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="When preference was saved",
    )

    def __repr__(self) -> str:
        return (
            f"<UserStorePreference(user_id={self.user_id!r}, saq_store_id={self.saq_store_id!r})>"
        )


class StockEvent(Base):
    """Records product availability transitions.

    saq_store_id is NULL for online events and non-NULL for in-store events.
    Emitted by the daily availability checker (--availability-check).
    """

    __tablename__ = "stock_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(
        String,
        ForeignKey("products.sku"),
        nullable=False,
        index=True,
        comment="Product that changed availability",
    )
    available = Column(
        Boolean,
        nullable=False,
        comment="New availability state (True=restock, False=destock)",
    )
    # NULL = online event; non-NULL = in-store event
    saq_store_id = Column(
        String,
        ForeignKey("stores.saq_store_id"),
        nullable=True,
        index=True,
        comment="Store where change was detected (NULL = online)",
    )
    detected_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="When the change was detected",
    )
    processed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When notifications were sent (NULL=pending)",
    )

    def __repr__(self) -> str:
        return (
            f"<StockEvent(sku={self.sku!r}, available={self.available!r}, "
            f"saq_store_id={self.saq_store_id!r})>"
        )
