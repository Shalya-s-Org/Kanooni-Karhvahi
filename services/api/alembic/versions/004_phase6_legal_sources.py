"""Phase 6 — legal_sources, legal_source_versions, and legal_source_chunks tables

Revision ID: 004_phase6_legal_sources
Revises: 003_phase5_analysis
Create Date: 2026-10-02

Establishes the curated legal sources catalogue for verified citation RAG.
Features:
  - Cryptographic content hashes (SHA-256) per version
  - Point-in-time temporal windows (effective_from, effective_to)
  - Structure-aware chunking preserving legal numbering
  - Vector embeddings for semantic search with pgvector (fallback to JSON)
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

try:
    from pgvector.sqlalchemy import Vector as _PgVector
    _PGVECTOR_AVAILABLE = True
except ImportError:
    _PgVector = None
    _PGVECTOR_AVAILABLE = False

revision: str = "004_phase6_legal_sources"
down_revision: Union[str, None] = "003_phase5_analysis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. legal_sources
    op.create_table(
        "legal_sources",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("source_type", sa.String(64), nullable=False, server_default="ACT"),
        sa.Column("authority", sa.String(255), nullable=False),
        sa.Column("official_url", sa.String(1024), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("jurisdiction", sa.String(64), nullable=False, server_default="India"),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("trust_level", sa.String(32), nullable=False, server_default="STATUTORY"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_legal_sources_name", "legal_sources", ["name"])
    op.create_index("ix_legal_sources_source_type", "legal_sources", ["source_type"])
    op.create_index("ix_legal_sources_jurisdiction", "legal_sources", ["jurisdiction"])
    op.create_index("ix_legal_sources_active", "legal_sources", ["active"])

    # 2. legal_source_versions
    op.create_table(
        "legal_source_versions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "legal_source_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("legal_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_identifier", sa.String(128), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publication_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("source_url", sa.String(1024), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_legal_source_versions_source_id", "legal_source_versions", ["legal_source_id"])
    op.create_index("ix_legal_source_versions_effective_from", "legal_source_versions", ["effective_from"])
    op.create_index("ix_legal_source_versions_effective_to", "legal_source_versions", ["effective_to"])

    # 3. legal_source_chunks
    chunk_columns = [
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "legal_source_version_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("legal_source_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("section", sa.String(128), nullable=True),
        sa.Column("subsection", sa.String(128), nullable=True),
        sa.Column("page_or_reference", sa.String(255), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_metadata", sa.JSON(), nullable=True),
    ]

    if _PGVECTOR_AVAILABLE and _PgVector is not None:
        chunk_columns.append(sa.Column("embedding", _PgVector(768), nullable=True))
    else:
        chunk_columns.append(sa.Column("embedding", sa.JSON(), nullable=True))

    op.create_table("legal_source_chunks", *chunk_columns)
    op.create_index("ix_legal_source_chunks_version_id", "legal_source_chunks", ["legal_source_version_id"])
    op.create_index("ix_legal_source_chunks_section", "legal_source_chunks", ["section"])


def downgrade() -> None:
    op.drop_table("legal_source_chunks")
    op.drop_table("legal_source_versions")
    op.drop_table("legal_sources")
