"""Create initial database schema

Revision ID: c87e0993c1ec
Revises:
Create Date: 2026-10-02 13:04:11.045720

Creates the two foundational tables required by all subsequent phase
migrations:

  - documents        : primary metadata record for uploaded legal documents
  - document_pages   : page-level extraction results (1:N child of documents)

Phase 3 / 4 / 5 tables (document_classifications, document_entities,
document_clauses, document_chunks, document_analyses, clause_analyses) are
created by their respective migrations and must NOT appear here.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c87e0993c1ec'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # documents
    # Primary metadata record for an uploaded legal document.
    # Columns match Document model in app/models/document.py.
    # created_at / updated_at inherited from app.database.base.Base.
    # ------------------------------------------------------------------
    op.create_table(
        'documents',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('session_id', sa.String(length=64), nullable=True),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('storage_key', sa.String(length=512), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('sha256_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('detected_language', sa.String(length=10), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=False),
        sa.Column('ocr_required', sa.Boolean(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('is_retryable', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_documents_expires_at'), 'documents', ['expires_at'], unique=False)
    op.create_index(op.f('ix_documents_session_id'), 'documents', ['session_id'], unique=False)
    op.create_index(op.f('ix_documents_sha256_hash'), 'documents', ['sha256_hash'], unique=False)
    op.create_index(op.f('ix_documents_status'), 'documents', ['status'], unique=False)

    # ------------------------------------------------------------------
    # document_pages
    # Page-level extraction results (N:1 → documents).
    # Columns match DocumentPage model in app/models/document.py.
    # created_at / updated_at inherited from app.database.base.Base.
    # ------------------------------------------------------------------
    op.create_table(
        'document_pages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('document_id', sa.Uuid(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('storage_key', sa.String(length=512), nullable=True),
        sa.Column('extracted_text', sa.Text(), nullable=False),
        sa.Column('ocr_used', sa.Boolean(), nullable=False),
        sa.Column('ocr_confidence', sa.Float(), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_document_pages_document_id'), 'document_pages', ['document_id'], unique=False)


def downgrade() -> None:
    # Drop in reverse dependency order (child before parent).
    op.drop_index(op.f('ix_document_pages_document_id'), table_name='document_pages')
    op.drop_table('document_pages')
    op.drop_index(op.f('ix_documents_status'), table_name='documents')
    op.drop_index(op.f('ix_documents_sha256_hash'), table_name='documents')
    op.drop_index(op.f('ix_documents_session_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_expires_at'), table_name='documents')
    op.drop_table('documents')
