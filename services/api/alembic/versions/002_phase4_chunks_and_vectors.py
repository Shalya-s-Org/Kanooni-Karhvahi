"""Phase 4 — document_chunks table with pgvector embedding column

Revision ID: 002_phase4_chunks
Revises: 001_phase3_intelligence
Create Date: 2026-09-25

Indexing strategy:
  An HNSW index (Hierarchical Navigable Small World) is created on the
  embedding column using cosine distance (vector_cosine_ops).

  HNSW is chosen over IVFFlat because:
    - It does not require a training phase (IVFFlat requires a populated
      table before the index can be built).
    - It provides better recall at equivalent query latency for small to
      medium datasets (< 1 M vectors).
    - It is the recommended index type for pgvector >= 0.5.0.

  Parameters:
    m=16           – number of connections per layer (default)
    ef_construction=64 – build-time beam width (default)

  These values work well for 768-dimensional vectors (Gemini text-embedding-004).
  Adjust m and ef_construction for very large corpora or different dimensions.

  The vector dimension (768) is set to match Gemini text-embedding-004 and
  can be changed here when a different model is selected.  Changing the
  dimension requires a migration to DROP and re-CREATE the embedding column
  and its index.

Cascade deletion:
  document_id → ON DELETE CASCADE (documents table)
  page_id     → ON DELETE CASCADE (document_pages table)
  clause_id   → ON DELETE CASCADE (document_clauses table)

  When a document is deleted, PostgreSQL automatically removes all its
  chunks (and therefore all embeddings) via the FK cascade.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# pgvector Alembic helper — provides the Vector column type for DDL generation.
try:
    from pgvector.sqlalchemy import Vector  # type: ignore[import]
    _PGVECTOR_AVAILABLE = True
except ImportError:
    _PGVECTOR_AVAILABLE = False

# ---------------------------------------------------------------------------
# Revision metadata
# ---------------------------------------------------------------------------
revision: str = "002_phase4_chunks"
down_revision: Union[str, None] = "001_phase3_intelligence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Embedding dimension — must match settings.EMBEDDING_DIMENSION.
VECTOR_DIM = 768


def upgrade() -> None:
    # 1. Ensure the pgvector extension is present (idempotent).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Create document_chunks table.
    if _PGVECTOR_AVAILABLE:
        embedding_col = sa.Column("embedding", Vector(VECTOR_DIM), nullable=True)
    else:
        # Fallback for environments where pgvector Python package is not
        # installed during migration generation (e.g. CI without the [db] extra).
        # The column is created as TEXT and must be manually altered to vector
        # type once pgvector is installed.
        embedding_col = sa.Column(
            "embedding",
            sa.Text(),
            nullable=True,
            comment=f"vector({VECTOR_DIM}) — install pgvector and run migration again",
        )

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "page_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("document_pages.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "clause_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("document_clauses.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("page_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("chunk_metadata", sa.JSON(), nullable=True),
        embedding_col,
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # 3. Scalar indexes for fast lookup by parent record.
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_page_id", "document_chunks", ["page_id"])
    op.create_index("ix_document_chunks_clause_id", "document_chunks", ["clause_id"])

    # 4. HNSW vector index for approximate nearest-neighbour search.
    #    Only created when pgvector is available (column type is vector).
    #    Skipped on fallback TEXT column — must be created manually after
    #    the column is properly converted to vector type.
    if _PGVECTOR_AVAILABLE:
        op.execute(
            f"CREATE INDEX ix_document_chunks_embedding_hnsw "
            f"ON document_chunks "
            f"USING hnsw (embedding vector_cosine_ops) "
            f"WITH (m = 16, ef_construction = 64)"
        )


def downgrade() -> None:
    op.drop_table("document_chunks")
