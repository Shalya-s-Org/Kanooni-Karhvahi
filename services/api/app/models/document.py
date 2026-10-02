import uuid
from datetime import datetime, timezone
from typing import Optional, List, Any
from sqlalchemy import String, Integer, Boolean, Float, Text, DateTime, ForeignKey, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

# pgvector SQLAlchemy integration — imported lazily to allow SQLite fallback in tests.
# The Vector type is only used when a real PostgreSQL+pgvector connection is available.
try:
    from pgvector.sqlalchemy import Vector as _PgVector  # type: ignore[import]
    _PGVECTOR_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PgVector = None
    _PGVECTOR_AVAILABLE = False


class Document(Base):
    """
    Primary metadata record for an uploaded legal document.
    Maintains integrity, processing lifecycle states, and 24-hour TTL expiration.
    """
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(32), default="UPLOADED", nullable=False, index=True)
    detected_language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ocr_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_retryable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships with cascade deletion for privacy and ephemeral cleanup
    pages: Mapped[List["DocumentPage"]] = relationship(
        "DocumentPage",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentPage.page_number"
    )
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index"
    )
    classification: Mapped[Optional["DocumentClassification"]] = relationship(
        "DocumentClassification",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan"
    )
    entities: Mapped[List["DocumentEntity"]] = relationship(
        "DocumentEntity",
        back_populates="document",
        cascade="all, delete-orphan"
    )
    clauses: Mapped[List["DocumentClause"]] = relationship(
        "DocumentClause",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentClause.page_start"
    )
    analyses: Mapped[List["DocumentAnalysis"]] = relationship(
        "DocumentAnalysis",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    clause_analyses: Mapped[List["ClauseAnalysis"]] = relationship(
        "ClauseAnalysis",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class DocumentPage(Base):
    """
    Extracted page-level information preserving exact page boundaries and OCR origins.
    """
    __tablename__ = "document_pages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    extracted_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ocr_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    document: Mapped["Document"] = relationship("Document", back_populates="pages")
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="page",
        cascade="all, delete-orphan"
    )
    entities: Mapped[List["DocumentEntity"]] = relationship(
        "DocumentEntity",
        back_populates="page",
        cascade="all, delete-orphan"
    )
    clauses: Mapped[List["DocumentClause"]] = relationship(
        "DocumentClause",
        back_populates="page",
        cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    """
    Semantic text chunk for pgvector-based retrieval (Phase 4).

    Each chunk is traceable to its source document → page → clause.
    The ``embedding`` column stores the dense vector produced by the
    configured embedding model.  It is nullable so that chunking can
    complete before embedding generation starts (and so the document can
    reach READY_WITHOUT_EMBEDDINGS if the embedding provider is unavailable).

    Cascade deletion:
      Document → Pages → Clauses → Chunks (via ON DELETE CASCADE FKs)
    """
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_pages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    clause_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_clauses.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    chunk_metadata: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # pgvector embedding column — dimension is set by migration/DDL.
    # Stored as native vector type; never serialised to JSON.
    # Nullable: set to NULL until embedding generation completes.
    if _PGVECTOR_AVAILABLE and _PgVector is not None:
        embedding: Mapped[Optional[List[float]]] = mapped_column(
            _PgVector(768),  # dimension overridden in migration via ALTER COLUMN
            nullable=True,
        )
    else:
        # SQLite fallback for tests — embedding stored as JSON array.
        # This path is ONLY used in the automated test suite; it is NEVER
        # exercised against a real PostgreSQL instance.
        embedding: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)  # type: ignore[assignment]

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
    page: Mapped[Optional["DocumentPage"]] = relationship("DocumentPage", back_populates="chunks")
    clause: Mapped[Optional["DocumentClause"]] = relationship("DocumentClause", back_populates="chunks")


class DocumentClassification(Base):
    """
    Broad legal document classification with confidence and traceable evidence snippets.
    """
    __tablename__ = "document_classifications"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    document_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[Any] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    document: Mapped["Document"] = relationship("Document", back_populates="classification")


class DocumentEntity(Base):
    """
    Action-relevant structured entity (dates, deadlines, amounts, parties, authorities, reference numbers, legal sections).
    Preserves exact page, source text excerpt, and character offsets.
    """
    __tablename__ = "document_entities"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    page_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_pages.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_value: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    entity_metadata: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    document: Mapped["Document"] = relationship("Document", back_populates="entities")
    page: Mapped[Optional["DocumentPage"]] = relationship("DocumentPage", back_populates="entities")


class DocumentClause(Base):
    """
    Logical clause or section segmented from the document text.
    Preserves original text, title, clause numbering, and source page span.
    """
    __tablename__ = "document_clauses"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    page_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_pages.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    clause_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    document: Mapped["Document"] = relationship("Document", back_populates="clauses")
    page: Mapped[Optional["DocumentPage"]] = relationship("DocumentPage", back_populates="clauses")
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="clause",
        cascade="all, delete-orphan",
    )
    analyses: Mapped[List["ClauseAnalysis"]] = relationship(
        "ClauseAnalysis",
        back_populates="clause",
        cascade="all, delete-orphan",
    )
