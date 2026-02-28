from datetime import UTC, datetime

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


class ProductAvailability(Base):
    """Per-product availability snapshot for watched SKUs.

    Online availability from GraphQL stock_status, store quantities from AJAX.
    Only contains rows for watched SKUs (not the full catalog).
    Updated daily by --check-watches.
    """

    __tablename__ = "product_availability"

    sku = Column(
        String,
        ForeignKey("products.sku"),
        primary_key=True,
        comment="Watched product SKU",
    )
    online_available = Column(
        Boolean,
        nullable=True,
        comment="Online availability from GraphQL stock_status (NULL = not yet checked)",
    )
    store_qty = Column(
        JSONB,
        nullable=False,
        default=dict,
        comment='Store stock map: {"23009": 44, "23132": 12}',
    )
    checked_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="When availability was last checked",
    )

    def __repr__(self) -> str:
        n = len(self.store_qty) if self.store_qty else 0
        online = self.online_available
        return f"<ProductAvailability(sku={self.sku!r}, online={online}, stores={n})>"


class StockEvent(Base):
    """Records product availability transitions.

    saq_store_id is NULL for online events and non-NULL for in-store events.
    Both are emitted by the daily availability checker (--check-watches).
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
