"""Add missing updated_at columns to Phase 3 intelligence tables

Revision ID: 005_add_updated_at
Revises: 004_phase6_legal_sources
Create Date: 2026-10-03

The Base class defines an `updated_at` column inherited by all SQLAlchemy
models. The Phase 3 migration (001_phase3_intelligence_tables) only added
`created_at` to document_classifications, document_entities, and
document_clauses, omitting `updated_at`.

When SQLAlchemy generates INSERT statements for these models it includes
`updated_at`, causing an UndefinedColumnError at the CLASSIFYING stage
that permanently stalls the document processing pipeline.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "005_add_updated_at"
down_revision: Union[str, None] = "004_phase6_legal_sources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "document_classifications",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.add_column(
        "document_entities",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.add_column(
        "document_clauses",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_column("document_clauses", "updated_at")
    op.drop_column("document_entities", "updated_at")
    op.drop_column("document_classifications", "updated_at")
