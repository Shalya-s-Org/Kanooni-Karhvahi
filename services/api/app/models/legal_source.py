"""
Legal source models for Phase 6 — Verified Legal-Source RAG.

Models:
  - LegalSource: Canonical catalog of authoritative legal sources (Acts, Rules, etc.)
  - LegalSourceVersion: Versioned, hash-verified snapshot with effective date windows
  - LegalSourceChunk: Structure-aware chunk with dense embedding vector
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

try:
    from pgvector.sqlalchemy import Vector as _PgVector  # type: ignore[import]
    _PGVECTOR_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PgVector = None
    _PGVECTOR_AVAILABLE = False


class LegalSourceType(str, Enum):
    ACT = "ACT"
    RULE = "RULE"
    REGULATION = "REGULATION"
    OFFICIAL_NOTIFICATION = "OFFICIAL_NOTIFICATION"
    COURT_JUDGMENT = "COURT_JUDGMENT"
    GOVERNMENT_GUIDANCE = "GOVERNMENT_GUIDANCE"
    OFFICIAL_FORM = "OFFICIAL_FORM"
    OTHER_OFFICIAL_SOURCE = "OTHER_OFFICIAL_SOURCE"


class LegalSource(Base):
    """
    Curated authority catalog entry (e.g. 'The Indian Contract Act, 1872').
    Never populated by arbitrary web crawling; requires explicit curation.
    """
    __tablename__ = "legal_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=LegalSourceType.ACT.value,
        index=True,
    )
    authority: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="e.g. 'Parliament of India', 'Supreme Court of India'",
    )
    official_url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        doc="Official government portal or gazette URL",
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    jurisdiction: Mapped[str] = mapped_column(
        String(64),
        default="India",
        nullable=False,
        index=True,
    )
    language: Mapped[str] = mapped_column(
        String(10),
        default="en",
        nullable=False,
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    trust_level: Mapped[str] = mapped_column(
        String(32),
        default="STATUTORY",
        nullable=False,
        doc="STATUTORY | OFFICIAL | JUDICIAL | REGULATORY",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    versions: Mapped[List["LegalSourceVersion"]] = relationship(
        "LegalSourceVersion",
        back_populates="source",
        cascade="all, delete-orphan",
        order_by="desc(LegalSourceVersion.retrieved_at)",
    )


class LegalSourceVersion(Base):
    """
    Specific temporal snapshot of a legal source with verifiable content hash.
    Preserves effective dates so historical documents can query the correct law.
    """
    __tablename__ = "legal_source_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    legal_source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("legal_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_identifier: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        doc="e.g. '1872-orig', '2015-amendment', 'v1.0'",
    )
    effective_from: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    effective_to: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    publication_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="SHA-256 hash of the complete ingested source text",
    )
    source_url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="ACTIVE",
        nullable=False,
        doc="ACTIVE | SUPERSEDED | DRAFT | ARCHIVED",
    )
    metadata_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    source: Mapped["LegalSource"] = relationship(
        "LegalSource",
        back_populates="versions",
    )
    chunks: Mapped[List["LegalSourceChunk"]] = relationship(
        "LegalSourceChunk",
        back_populates="version",
        cascade="all, delete-orphan",
        order_by="LegalSourceChunk.chunk_index",
    )


class LegalSourceChunk(Base):
    """
    Structure-aware chunk from a legal source version.
    Preserves exact section, subsection, and article numbering.
    """
    __tablename__ = "legal_source_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    legal_source_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("legal_source_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    section: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        index=True,
        doc="e.g. 'Section 73', 'Article 21', 'Order 39'",
    )
    subsection: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        doc="e.g. '(1)', '(2)(a)'",
    )
    page_or_reference: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="e.g. 'Chapter VI, Page 14'",
    )
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_metadata: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Vector embedding column with SQLite fallback
    if _PGVECTOR_AVAILABLE and _PgVector is not None:
        embedding: Mapped[Optional[List[float]]] = mapped_column(
            _PgVector(768),
            nullable=True,
        )
    else:
        embedding: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Relationship
    version: Mapped["LegalSourceVersion"] = relationship(
        "LegalSourceVersion",
        back_populates="chunks",
    )
