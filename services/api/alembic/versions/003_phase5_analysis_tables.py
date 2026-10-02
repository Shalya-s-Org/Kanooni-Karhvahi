"""Phase 5 — document_analyses and clause_analyses tables

Revision ID: 003_phase5_analysis
Revises: 002_phase4_chunks
Create Date: 2026-09-25

Both tables cascade-delete when their parent document is removed.
ClauseAnalysis also cascades when the parent clause is removed.

Analysis lifecycle:
  PENDING → GENERATING → COMPLETED | VALIDATION_FAILED | FAILED | PROVIDER_UNAVAILABLE

Privacy:
  These tables never contain API keys, binary document data, or embeddings.
  They only store structured JSON outputs and the evidence snapshot submitted
  to the LLM.  When a document expires (24-hour TTL), ON DELETE CASCADE
  removes both tables automatically.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003_phase5_analysis"
down_revision: Union[str, None] = "002_phase4_chunks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # document_analyses
    # -----------------------------------------------------------------------
    op.create_table(
        "document_analyses",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("analysis_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=32), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
    op.create_index("ix_document_analyses_document_id", "document_analyses", ["document_id"])
    op.create_index("ix_document_analyses_status", "document_analyses", ["status"])
    op.create_index("ix_document_analyses_analysis_type", "document_analyses", ["analysis_type"])

    # -----------------------------------------------------------------------
    # clause_analyses
    # -----------------------------------------------------------------------
    op.create_table(
        "clause_analyses",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "clause_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("document_clauses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=32), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
    op.create_index("ix_clause_analyses_document_id", "clause_analyses", ["document_id"])
    op.create_index("ix_clause_analyses_clause_id", "clause_analyses", ["clause_id"])
    op.create_index("ix_clause_analyses_status", "clause_analyses", ["status"])


def downgrade() -> None:
    op.drop_table("clause_analyses")
    op.drop_table("document_analyses")
