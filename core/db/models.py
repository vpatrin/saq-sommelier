from datetime import UTC, date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
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
from core.embedding_constants import EMBEDDING_DIMENSIONS


class User(Base):
    """Registered user — identity linked via OAuth providers (oauth_accounts table)."""

    __tablename__ = "users"
    __table_args__ = (CheckConstraint("locale IN ('fr', 'en')", name="ck_users_locale"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(
        String(254),
        unique=True,
        nullable=False,
        comment="Primary email from OAuth provider (lowercased)",
    )
    display_name = Column(String, nullable=True, comment="User-set display name")
    telegram_id = Column(
        BigInteger,
        unique=True,
        nullable=True,
        index=True,
        comment="Telegram user ID — notification channel only, not an auth credential",
    )
    role = Column(
        String(20),
        nullable=False,
        default="user",
        comment="Authorization role: user or admin",
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Admin kill-switch — False blocks login regardless of status",
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="When user first registered",
    )
    locale = Column(
        String(5),
        nullable=True,
        comment="Preferred UI locale (fr, en) — NULL = use browser default",
    )
    last_login_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful login (updated on each auth)",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id!r}, email={self.email!r}, role={self.role!r})>"


class OAuthAccount(Base):
    """OAuth provider account linked to a user — supports multiple providers per user."""

    __tablename__ = "oauth_accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_oauth_accounts_provider_uid"),
        CheckConstraint("provider IN ('github', 'google')", name="ck_oauth_accounts_provider"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owning user",
    )
    provider = Column(String(20), nullable=False, comment="OAuth provider: github or google")
    provider_user_id = Column(String, nullable=False, comment="Provider's stable user identifier")
    email = Column(
        String(254),
        nullable=False,
        comment="Email from provider at time of linking (may differ from users.email)",
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="When this provider account was linked",
    )

    def __repr__(self) -> str:
        return (
            f"<OAuthAccount(user_id={self.user_id!r}, provider={self.provider!r}, "
            f"provider_user_id={self.provider_user_id!r})>"
        )


class WaitlistRequest(Base):
    """Pre-auth waitlist request — exists before a User row is created.

    A User row is only created on first OAuth login after approval.
    status: pending (awaiting admin review) | approved (can log in) | rejected
    """

    __tablename__ = "waitlist_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_waitlist_requests_status",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(
        String(254),
        unique=True,
        nullable=False,
        index=True,
        comment="Applicant email — lowercased at write time",
    )
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending | approved | rejected",
    )
    email_sent_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the approval email was last sent (NULL = not sent yet)",
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="When the request was submitted",
    )
    approved_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the request was approved",
    )

    def __repr__(self) -> str:
        return f"<WaitlistRequest(id={self.id!r}, email={self.email!r}, status={self.status!r})>"


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
    last_scraped_hash = Column(
        String,
        nullable=True,
        comment="SHA256 of scraped ProductData fields — skip write when unchanged",
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

    # Wine attributes (writer: enrich subcommand)
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

    # Availability (writer: availability subcommand)
    store_availability = Column(
        JSONB,
        nullable=True,
        comment='Store IDs carrying this product: ["23002","23004",...]',
    )

    # Embedding support (writer: embed subcommand)
    embedding = Column(
        Vector(EMBEDDING_DIMENSIONS),
        nullable=True,
        comment="Wine semantic embedding (text-embedding-3-large, 1536d)",
    )
    last_embedded_hash = Column(
        String,
        nullable=True,
        comment="Hash of embedding-relevant fields at last embed sync",
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
    Emitted by the daily availability checker (availability subcommand).
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


class RecommendationLog(Base):
    """Captures each /recommend request for ML observability and feedback tracking."""

    __tablename__ = "recommendation_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        String,
        nullable=True,
        index=True,
        comment="Channel-prefixed user ID (e.g. tg:123456)",
    )
    query = Column(Text, nullable=False, comment="Raw user input")
    parsed_intent = Column(JSONB, nullable=True, comment="Structured intent from Claude")
    returned_skus = Column(JSONB, nullable=True, comment="Ordered list of recommended SKUs")
    product_count = Column(Integer, nullable=False, default=0, comment="Number of results returned")
    latency_ms = Column(JSONB, nullable=True, comment="Per-stage timing breakdown")
    feedback = Column(String, nullable=True, comment="User feedback: positive or negative")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
        comment="When the recommendation was requested",
    )

    def __repr__(self) -> str:
        return f"<RecommendationLog(id={self.id!r}, query={self.query!r})>"


class ChatSession(Base):
    """Conversation session for the web chat interface."""

    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Owner of this chat session",
    )
    title = Column(
        String,
        nullable=True,
        comment="Auto-generated from first message (~50 chars)",
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="When session was started",
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        comment="Last message timestamp",
    )

    __table_args__ = (Index("ix_chat_sessions_user_updated", "user_id", "updated_at"),)

    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id!r}, user_id={self.user_id!r})>"


class ChatMessage(Base):
    """Individual message within a chat session."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        Integer,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        comment="Parent chat session",
    )
    role = Column(
        String(20),
        nullable=False,
        comment="Message author: user or assistant",
    )
    content = Column(Text, nullable=False, comment="Message text content")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="When message was sent",
    )

    __table_args__ = (Index("ix_chat_messages_session_created", "session_id", "created_at"),)


class TastingNote(Base):
    """User tasting note for a wine — one or more per SKU (Untappd model)."""

    __tablename__ = "tasting_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        String,
        nullable=False,
        comment="Channel-prefixed user ID (e.g. tg:123456)",
    )
    sku = Column(
        String,
        ForeignKey("products.sku"),
        nullable=False,
        comment="Tasted product SKU",
    )
    rating = Column(Integer, nullable=False, comment="Parker-style rating 0-100")
    notes = Column(Text, nullable=True, comment="Free-text tasting notes")
    pairing = Column(Text, nullable=True, comment="Free-text food pairing")
    tasted_at = Column(
        Date,
        nullable=False,
        default=lambda: date.today(),
        comment="Date the wine was tasted",
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="When note was created",
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        comment="When note was last updated",
    )

    __table_args__ = (
        Index("ix_tasting_notes_user_id", "user_id"),
        Index("ix_tasting_notes_sku", "sku"),
        CheckConstraint("rating >= 0 AND rating <= 100", name="ck_tasting_notes_rating"),
    )
