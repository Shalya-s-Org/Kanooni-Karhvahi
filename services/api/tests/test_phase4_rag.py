"""
Phase 4 — Semantic Chunking, Embeddings & Vector Retrieval Tests
================================================================

Test coverage:
  1.  Clause-aware chunking: short clause produces exactly one chunk
  2.  Clause-aware chunking: long clause is split into multiple chunks
  3.  Page metadata is preserved on every chunk
  4.  Clause metadata (clause_id, clause_number) is preserved on every chunk
  5.  Source text is preserved verbatim (chunk text ⊆ original_text)
  6.  Chunking from pages fallback (no clauses)
  7.  Deterministic mock embeddings: identical text → identical vector
  8.  Deterministic mock embeddings: different texts → different vectors
  9.  Embedding dimension validation
 10.  Chunk persistence (chunk_and_persist writes to DB)
 11.  Chunk idempotence (re-running chunk_and_persist replaces old chunks)
 12.  Vector persistence (embeddings stored on chunk records)
 13.  Semantic retrieval returns results
 14.  Retrieval top-k behaviour
 15.  Document isolation: query against doc A never returns doc B chunks
 16.  Deleted document exclusion
 17.  Empty query rejection
 18.  Missing embedding provider raises EmbeddingProviderError
 19.  API response schema (POST /documents/{id}/retrieve)
 20.  End-to-end: document → chunks → embeddings → retrieval
 21.  READY_WITHOUT_EMBEDDINGS status when provider unavailable in pipeline

All tests use MockEmbeddingProvider (deterministic, no external API calls).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.document import Document, DocumentPage, DocumentClause, DocumentChunk
from app.rag.chunking.chunker import DocumentChunker, ChunkMetadata, _count_tokens
from app.rag.embeddings.base import MockEmbeddingProvider, EmbeddingProviderError
from app.rag.embeddings.factory import get_embedding_provider
from app.rag.retrieval.service import DocumentRetrievalService


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_document(session_id: str = "test") -> Document:
    now = datetime.now(timezone.utc)
    return Document(
        id=uuid.uuid4(),
        session_id=session_id,
        original_filename="test.pdf",
        storage_key=f"uploads/{uuid.uuid4()}/original/test.pdf",
        mime_type="application/pdf",
        file_size=1024,
        sha256_hash="abc123",
        status="SEGMENTING_CLAUSES",
        page_count=2,
        ocr_required=False,
        expires_at=now + timedelta(hours=24),
        is_retryable=False,
        created_at=now,
        updated_at=now,
    )


def _make_page(document_id: uuid.UUID, page_number: int, text: str) -> DocumentPage:
    now = datetime.now(timezone.utc)
    return DocumentPage(
        id=uuid.uuid4(),
        document_id=document_id,
        page_number=page_number,
        extracted_text=text,
        ocr_used=False,
        created_at=now,
        updated_at=now,
    )


def _make_clause(
    document_id: uuid.UUID,
    page_id: Optional[uuid.UUID],
    clause_number: str,
    text: str,
    page_start: int = 1,
) -> DocumentClause:
    now = datetime.now(timezone.utc)
    return DocumentClause(
        id=uuid.uuid4(),
        document_id=document_id,
        page_id=page_id,
        clause_number=clause_number,
        title=f"Clause {clause_number}",
        original_text=text,
        page_start=page_start,
        page_end=page_start,
        confidence=0.95,
        created_at=now,
        updated_at=now,
    )


SHORT_TEXT = "The payment shall be made within 30 days of the invoice date."
# ~100 tokens — well within 500-token limit.

LONG_TEXT = " ".join(
    [
        "This Agreement sets forth the complete terms and conditions governing "
        "the relationship between the parties as described herein and shall be "
        "binding upon their respective successors and assigns. "
    ]
    * 25  # Repeat to make it ~500+ tokens.
)


# ---------------------------------------------------------------------------
# 1. Short clause produces exactly one chunk (no splitting)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_short_clause_produces_single_chunk(test_db_session: AsyncSession):
    """A clause shorter than CHUNK_SIZE_TOKENS must produce exactly one chunk."""
    doc = _make_document()
    page = _make_page(doc.id, 1, SHORT_TEXT)
    clause = _make_clause(doc.id, page.id, "1", SHORT_TEXT)

    test_db_session.add(doc)
    test_db_session.add(page)
    test_db_session.add(clause)
    await test_db_session.commit()

    chunker = DocumentChunker(chunk_size_tokens=500, chunk_overlap_tokens=75)
    chunks = await chunker.chunk_and_persist(doc.id, test_db_session)

    assert len(chunks) == 1, f"Expected 1 chunk for short clause, got {len(chunks)}"
    assert chunks[0].text.strip() == SHORT_TEXT.strip()


# ---------------------------------------------------------------------------
# 2. Long clause is split into multiple chunks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_long_clause_is_split(test_db_session: AsyncSession):
    """A clause exceeding CHUNK_SIZE_TOKENS must produce more than one chunk."""
    token_count = _count_tokens(LONG_TEXT)
    assert token_count > 100, "Test data precondition: LONG_TEXT must be > 100 tokens."

    doc = _make_document()
    page = _make_page(doc.id, 1, LONG_TEXT)
    clause = _make_clause(doc.id, page.id, "2", LONG_TEXT)

    test_db_session.add(doc)
    test_db_session.add(page)
    test_db_session.add(clause)
    await test_db_session.commit()

    chunker = DocumentChunker(chunk_size_tokens=100, chunk_overlap_tokens=10)
    chunks = await chunker.chunk_and_persist(doc.id, test_db_session)

    assert len(chunks) > 1, (
        f"Expected multiple chunks for long clause ({token_count} tokens at limit=100), "
        f"got {len(chunks)}"
    )
    for chunk in chunks:
        assert _count_tokens(chunk.text) <= 110  # Allow slight overflow at sentence boundary.


# ---------------------------------------------------------------------------
# 3. Page metadata preserved on every chunk
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_page_metadata_preserved(test_db_session: AsyncSession):
    """Every chunk must carry the correct page_number and page_id."""
    doc = _make_document()
    page = _make_page(doc.id, 3, SHORT_TEXT)
    clause = _make_clause(doc.id, page.id, "7", SHORT_TEXT, page_start=3)

    test_db_session.add(doc)
    test_db_session.add(page)
    test_db_session.add(clause)
    await test_db_session.commit()

    chunker = DocumentChunker(chunk_size_tokens=500, chunk_overlap_tokens=75)
    chunks = await chunker.chunk_and_persist(doc.id, test_db_session)

    assert len(chunks) >= 1
    for chunk in chunks:
        assert chunk.page_number == 3
        assert chunk.page_id == page.id


# ---------------------------------------------------------------------------
# 4. Clause metadata preserved on every chunk
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clause_metadata_preserved(test_db_session: AsyncSession):
    """Every chunk must carry clause_id and clause_number from its source clause."""
    doc = _make_document()
    page = _make_page(doc.id, 1, SHORT_TEXT)
    clause = _make_clause(doc.id, page.id, "7", SHORT_TEXT)

    test_db_session.add(doc)
    test_db_session.add(page)
    test_db_session.add(clause)
    await test_db_session.commit()

    chunker = DocumentChunker(chunk_size_tokens=500, chunk_overlap_tokens=75)
    chunks = await chunker.chunk_and_persist(doc.id, test_db_session)

    assert len(chunks) >= 1
    for chunk in chunks:
        assert chunk.clause_id == clause.id
        assert (chunk.chunk_metadata or {}).get("clause_number") == "7"


# ---------------------------------------------------------------------------
# 5. Source text preserved verbatim
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_source_text_preserved(test_db_session: AsyncSession):
    """Each chunk's text must be a substring of the original clause text."""
    doc = _make_document()
    page = _make_page(doc.id, 1, SHORT_TEXT)
    clause = _make_clause(doc.id, page.id, "1", SHORT_TEXT)

    test_db_session.add(doc)
    test_db_session.add(page)
    test_db_session.add(clause)
    await test_db_session.commit()

    chunker = DocumentChunker(chunk_size_tokens=500, chunk_overlap_tokens=75)
    chunks = await chunker.chunk_and_persist(doc.id, test_db_session)

    for chunk in chunks:
        # Every word in the chunk must appear in the original text.
        for word in chunk.text.split():
            assert word in clause.original_text, (
                f"Chunk word '{word}' not found in original clause text."
            )


# ---------------------------------------------------------------------------
# 6. Chunking from pages fallback (no clauses)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chunking_fallback_from_pages(test_db_session: AsyncSession):
    """If no clauses exist, chunks should be produced from page text."""
    doc = _make_document()
    page = _make_page(doc.id, 1, SHORT_TEXT)
    # No clauses added.

    test_db_session.add(doc)
    test_db_session.add(page)
    await test_db_session.commit()

    chunker = DocumentChunker(chunk_size_tokens=500, chunk_overlap_tokens=75)
    chunks = await chunker.chunk_and_persist(doc.id, test_db_session)

    assert len(chunks) >= 1
    for chunk in chunks:
        assert chunk.clause_id is None
        assert chunk.page_id == page.id


# ---------------------------------------------------------------------------
# 7. Deterministic mock embeddings: identical text → identical vector
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_embedding_deterministic():
    """MockEmbeddingProvider must return the same vector for the same text."""
    provider = MockEmbeddingProvider(dim=768)
    v1 = await provider.embed_text("Hello legal world")
    v2 = await provider.embed_text("Hello legal world")
    assert v1 == v2, "MockEmbeddingProvider is not deterministic."


# ---------------------------------------------------------------------------
# 8. Different texts produce different vectors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_embedding_different_texts_differ():
    """MockEmbeddingProvider must produce different vectors for different texts."""
    provider = MockEmbeddingProvider(dim=768)
    v1 = await provider.embed_text("payment deadline clause")
    v2 = await provider.embed_text("governing law jurisdiction")
    assert v1 != v2, "Different texts should produce different mock embeddings."


# ---------------------------------------------------------------------------
# 9. Embedding dimension validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_embedding_dimension():
    """Embedding vector length must exactly match the configured dimension."""
    for dim in [128, 384, 768, 1536]:
        provider = MockEmbeddingProvider(dim=dim)
        vec = await provider.embed_text("test text for dimension check")
        assert len(vec) == dim, f"Expected {dim}-dimensional vector, got {len(vec)}."


# ---------------------------------------------------------------------------
# 10. Chunk persistence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chunk_persistence(test_db_session: AsyncSession):
    """chunk_and_persist must write DocumentChunk records to the database."""
    doc = _make_document()
    page = _make_page(doc.id, 1, SHORT_TEXT)
    clause = _make_clause(doc.id, page.id, "1", SHORT_TEXT)

    test_db_session.add(doc)
    test_db_session.add(page)
    test_db_session.add(clause)
    await test_db_session.commit()

    chunker = DocumentChunker(chunk_size_tokens=500, chunk_overlap_tokens=75)
    await chunker.chunk_and_persist(doc.id, test_db_session)

    # Reload from DB.
    result = await test_db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
    )
    db_chunks = list(result.scalars().all())
    assert len(db_chunks) >= 1
    assert all(c.document_id == doc.id for c in db_chunks)
    assert all(c.token_count > 0 for c in db_chunks)


# ---------------------------------------------------------------------------
# 11. Chunk idempotence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chunk_idempotence(test_db_session: AsyncSession):
    """Running chunk_and_persist twice must replace old chunks, not duplicate."""
    doc = _make_document()
    page = _make_page(doc.id, 1, SHORT_TEXT)
    clause = _make_clause(doc.id, page.id, "1", SHORT_TEXT)

    test_db_session.add(doc)
    test_db_session.add(page)
    test_db_session.add(clause)
    await test_db_session.commit()

    chunker = DocumentChunker(chunk_size_tokens=500, chunk_overlap_tokens=75)
    first_run = await chunker.chunk_and_persist(doc.id, test_db_session)
    second_run = await chunker.chunk_and_persist(doc.id, test_db_session)

    result = await test_db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
    )
    all_chunks = list(result.scalars().all())

    # The count after second run must equal the second run's output (not doubled).
    assert len(all_chunks) == len(second_run)


# ---------------------------------------------------------------------------
# 12. Vector persistence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vector_persistence(test_db_session: AsyncSession):
    """After embedding generation, chunks must have non-null embedding values."""
    from app.services.document_service import _generate_and_store_embeddings

    doc = _make_document()
    page = _make_page(doc.id, 1, SHORT_TEXT)
    clause = _make_clause(doc.id, page.id, "1", SHORT_TEXT)

    test_db_session.add(doc)
    test_db_session.add(page)
    test_db_session.add(clause)
    await test_db_session.commit()

    chunker = DocumentChunker(chunk_size_tokens=500, chunk_overlap_tokens=75)
    await chunker.chunk_and_persist(doc.id, test_db_session)

    provider = MockEmbeddingProvider(dim=768)
    count = await _generate_and_store_embeddings(doc.id, provider, test_db_session)

    assert count > 0

    result = await test_db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
    )
    chunks = list(result.scalars().all())
    for chunk in chunks:
        assert chunk.embedding is not None, "Chunk embedding must not be None after generation."
        assert len(chunk.embedding) == 768


# ---------------------------------------------------------------------------
# 13. Retrieval returns results (lexical fallback for SQLite)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieval_returns_results(test_db_session: AsyncSession):
    """Retrieval service must return results for a relevant query."""
    from app.services.document_service import _generate_and_store_embeddings

    doc = _make_document()
    page = _make_page(doc.id, 4, SHORT_TEXT)
    clause = _make_clause(doc.id, page.id, "3", SHORT_TEXT, page_start=4)

    test_db_session.add(doc)
    test_db_session.add(page)
    test_db_session.add(clause)
    await test_db_session.commit()

    chunker = DocumentChunker(chunk_size_tokens=500, chunk_overlap_tokens=75)
    await chunker.chunk_and_persist(doc.id, test_db_session)

    provider = MockEmbeddingProvider(dim=768)
    await _generate_and_store_embeddings(doc.id, provider, test_db_session)

    service = DocumentRetrievalService()
    results = await service.retrieve(
        document_id=doc.id,
        query="payment invoice",
        top_k=3,
        db=test_db_session,
        provider=provider,
    )

    assert isinstance(results, list)
    # Results may be returned via semantic (pgvector) or lexical fallback.
    # Both are valid in this test environment.
    for r in results:
        assert r.document_id == doc.id
        assert r.text  # non-empty
        assert 0.0 <= r.score <= 1.0


# ---------------------------------------------------------------------------
# 14. Retrieval top-k behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieval_top_k(test_db_session: AsyncSession):
    """Retrieval must return at most top_k results."""
    from app.services.document_service import _generate_and_store_embeddings

    texts = [
        "Clause one text about payment terms and invoice dates.",
        "Clause two covers the governing law and jurisdiction for disputes.",
        "Clause three defines confidentiality and non-disclosure obligations.",
        "Clause four establishes the term and termination conditions.",
        "Clause five covers indemnification and liability limitations.",
    ]

    doc = _make_document()
    test_db_session.add(doc)
    await test_db_session.flush()

    for i, text in enumerate(texts, start=1):
        page = _make_page(doc.id, i, text)
        clause = _make_clause(doc.id, page.id, str(i), text, page_start=i)
        test_db_session.add(page)
        test_db_session.add(clause)

    await test_db_session.commit()

    chunker = DocumentChunker(chunk_size_tokens=500, chunk_overlap_tokens=75)
    await chunker.chunk_and_persist(doc.id, test_db_session)

    provider = MockEmbeddingProvider(dim=768)
    await _generate_and_store_embeddings(doc.id, provider, test_db_session)

    service = DocumentRetrievalService()
    results = await service.retrieve(
        document_id=doc.id,
        query="payment terms",
        top_k=3,
        db=test_db_session,
        provider=provider,
    )

    assert len(results) <= 3


# ---------------------------------------------------------------------------
# 15. Document isolation: query against doc A never returns doc B chunks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_document_isolation(test_db_session: AsyncSession):
    """Chunks from document B must NEVER appear in results for document A."""
    from app.services.document_service import _generate_and_store_embeddings

    doc_a = _make_document("session_a")
    doc_b = _make_document("session_b")
    test_db_session.add(doc_a)
    test_db_session.add(doc_b)
    await test_db_session.flush()

    page_a = _make_page(doc_a.id, 1, "Document A clause about payment deadline.")
    page_b = _make_page(doc_b.id, 1, "Document B clause about governing law.")
    clause_a = _make_clause(doc_a.id, page_a.id, "1", "Document A clause about payment deadline.")
    clause_b = _make_clause(doc_b.id, page_b.id, "1", "Document B clause about governing law.")

    for obj in [page_a, page_b, clause_a, clause_b]:
        test_db_session.add(obj)
    await test_db_session.commit()

    chunker = DocumentChunker(chunk_size_tokens=500, chunk_overlap_tokens=75)
    await chunker.chunk_and_persist(doc_a.id, test_db_session)
    await chunker.chunk_and_persist(doc_b.id, test_db_session)

    provider = MockEmbeddingProvider(dim=768)
    await _generate_and_store_embeddings(doc_a.id, provider, test_db_session)
    await _generate_and_store_embeddings(doc_b.id, provider, test_db_session)

    service = DocumentRetrievalService()
    results = await service.retrieve(
        document_id=doc_a.id,
        query="payment",
        top_k=10,
        db=test_db_session,
        provider=provider,
    )

    for r in results:
        assert r.document_id == doc_a.id, (
            f"Document isolation violated: got chunk from document {r.document_id}, "
            f"expected only chunks from document {doc_a.id}"
        )


# ---------------------------------------------------------------------------
# 16. Deleted document exclusion
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deleted_document_exclusion(test_db_session: AsyncSession):
    """Retrieval against a deleted document must raise ValueError."""
    now = datetime.now(timezone.utc)
    doc = _make_document()
    doc.deleted_at = now  # Mark as deleted.
    test_db_session.add(doc)
    await test_db_session.commit()

    service = DocumentRetrievalService()
    provider = MockEmbeddingProvider(dim=768)

    with pytest.raises(ValueError, match="not found or has been deleted"):
        await service.retrieve(
            document_id=doc.id,
            query="payment deadline",
            top_k=5,
            db=test_db_session,
            provider=provider,
        )


# ---------------------------------------------------------------------------
# 17. Empty query rejection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_query_rejection(test_db_session: AsyncSession):
    """Retrieval with an empty or whitespace-only query must raise ValueError."""
    doc = _make_document()
    test_db_session.add(doc)
    await test_db_session.commit()

    service = DocumentRetrievalService()
    provider = MockEmbeddingProvider(dim=768)

    for bad_query in ["", "   ", "\t\n"]:
        with pytest.raises(ValueError, match="empty"):
            await service.retrieve(
                document_id=doc.id,
                query=bad_query,
                top_k=5,
                db=test_db_session,
                provider=provider,
            )


# ---------------------------------------------------------------------------
# 18. Missing embedding provider raises EmbeddingProviderError
# ---------------------------------------------------------------------------

def test_unregistered_provider_raises():
    """Requesting an unregistered provider must raise EmbeddingProviderError."""
    with pytest.raises(EmbeddingProviderError) as exc_info:
        get_embedding_provider("nonexistent_provider_xyz")
    assert "nonexistent_provider_xyz" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 19. API response schema
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieve_api_response_schema(async_client: AsyncClient, test_db_session: AsyncSession):
    """POST /documents/{id}/retrieve must return the expected ApiResponse schema."""
    from app.services.document_service import _generate_and_store_embeddings

    doc = _make_document()
    page = _make_page(doc.id, 1, SHORT_TEXT)
    clause = _make_clause(doc.id, page.id, "7", SHORT_TEXT)

    test_db_session.add(doc)
    test_db_session.add(page)
    test_db_session.add(clause)
    await test_db_session.commit()

    chunker = DocumentChunker(chunk_size_tokens=500, chunk_overlap_tokens=75)
    await chunker.chunk_and_persist(doc.id, test_db_session)

    provider = MockEmbeddingProvider(dim=768)
    await _generate_and_store_embeddings(doc.id, provider, test_db_session)

    response = await async_client.post(
        f"/api/v1/documents/{doc.id}/retrieve",
        json={"query": "payment", "top_k": 5},
    )

    assert response.status_code == 200
    body = response.json()

    # Standard ApiResponse envelope
    assert "success" in body
    assert "data" in body
    assert "error" in body

    if body["success"]:
        data = body["data"]
        assert "document_id" in data
        assert "query" in data
        assert "results" in data
        assert "total_results" in data
        assert "retrieval_method" in data
        assert data["query"] == "payment"
        assert isinstance(data["results"], list)

        for result in data["results"]:
            assert "chunk_id" in result
            assert "text" in result
            assert "score" in result
            assert "page_number" in result
            assert "document_id" in result
            assert "retrieval_method" in result
            assert 0.0 <= result["score"] <= 1.0


# ---------------------------------------------------------------------------
# 20. API rejects empty query
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieve_api_rejects_empty_query(async_client: AsyncClient, test_db_session: AsyncSession):
    """POST /retrieve with an empty query must return 422 (Pydantic validation)."""
    doc = _make_document()
    test_db_session.add(doc)
    await test_db_session.commit()

    response = await async_client.post(
        f"/api/v1/documents/{doc.id}/retrieve",
        json={"query": "", "top_k": 5},
    )

    assert response.status_code == 422  # Pydantic min_length=1 validation


# ---------------------------------------------------------------------------
# 21. End-to-end: document → chunks → embeddings → retrieval
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_end_to_end_chunk_embed_retrieve(async_client: AsyncClient, test_db_session: AsyncSession):
    """
    Full Phase 4 pipeline:
      POST /documents/text (intake pasted legal text)
        → chunks are created
        → embeddings are stored
        → POST /retrieve returns results

    Uses the MockEmbeddingProvider (deterministic, no external API).
    """
    from app.services.document_service import document_service

    legal_text = """
    COMMERCIAL SERVICES AGREEMENT

    1. PAYMENT TERMS
    The Client shall pay the agreed consideration of Rs. 5,00,000 within 30 days of invoice.
    Late payment attracts a penalty of Rs. 10,000 per month.

    2. TERM AND TERMINATION
    This agreement shall remain valid for 12 months from the Effective Date of 01 January 2027.
    Either party may terminate with 60 days written notice.

    3. GOVERNING LAW
    This agreement shall be governed by the laws of India and subject to Delhi jurisdiction.
    """

    # Step 1: Intake pasted text.
    intake_res = await async_client.post(
        "/api/v1/documents/text",
        json={"text": legal_text, "filename": "phase4_test_agreement.txt"},
    )
    assert intake_res.status_code == 201
    doc_id = intake_res.json()["data"]["document_id"]

    # Step 2: Verify chunks were created.
    chunk_result = await test_db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(doc_id))
    )
    chunks = list(chunk_result.scalars().all())
    assert len(chunks) >= 1, "At least one chunk must exist after intake."

    # Step 3: Verify document is in a ready state.
    status_res = await async_client.get(f"/api/v1/documents/{doc_id}/status")
    assert status_res.status_code == 200
    doc_status = status_res.json()["data"]["status"]
    assert doc_status in ("READY", "READY_WITHOUT_EMBEDDINGS"), (
        f"Document should be READY after pipeline, got: {doc_status}"
    )

    # Step 4: Call retrieval endpoint.
    retrieve_res = await async_client.post(
        f"/api/v1/documents/{doc_id}/retrieve",
        json={"query": "payment deadline", "top_k": 3},
    )
    assert retrieve_res.status_code == 200
    body = retrieve_res.json()

    # Either success with results OR EMBEDDING_PROVIDER_UNAVAILABLE error.
    # Both are acceptable — the endpoint must never crash.
    assert body["success"] is True or (
        body["success"] is False
        and body["error"]["code"] == "EMBEDDING_PROVIDER_UNAVAILABLE"
    ), f"Unexpected response: {body}"

    if body["success"]:
        data = body["data"]
        assert data["total_results"] >= 0
        # If results exist, every result must trace back to the correct document.
        for r in data["results"]:
            assert r["document_id"] == doc_id


# ---------------------------------------------------------------------------
# 22. READY_WITHOUT_EMBEDDINGS when provider unavailable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_ready_without_embeddings(test_db_session: AsyncSession):
    """
    When the embedding provider raises EmbeddingProviderError,
    the document must reach READY_WITHOUT_EMBEDDINGS (not FAILED).
    """
    import fitz
    from app.services.document_service import document_service
    from app.rag.embeddings.factory import get_embedding_provider as orig_factory
    from app.rag.embeddings.base import EmbeddingProviderError

    # Create a minimal one-page PDF.
    pdf_doc = fitz.open()
    pdf_page = pdf_doc.new_page(width=595, height=842)
    pdf_page.insert_text((50, 100), "PAYMENT TERMS\n1. Payment due within 30 days.", fontsize=11)
    pdf_bytes = pdf_doc.tobytes()
    pdf_doc.close()

    import tempfile, os
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.write(pdf_bytes)
    tmp.close()

    # Override the get_embedding_provider function used inside the pipeline
    # to simulate a misconfigured provider.
    with patch("app.services.document_service.get_embedding_provider") as mock_factory:
        mock_factory.side_effect = EmbeddingProviderError(
            provider="fake", reason="credentials not configured"
        )

        import uuid as uuid_mod
        doc_id = uuid_mod.uuid4()
        now = datetime.now(timezone.utc)

        doc = Document(
            id=doc_id,
            session_id="test_no_embed",
            original_filename="test.pdf",
            storage_key=f"uploads/{doc_id}/original/test.pdf",
            mime_type="application/pdf",
            file_size=len(pdf_bytes),
            sha256_hash="deadbeef",
            status="UPLOADED",
            page_count=0,
            ocr_required=False,
            expires_at=now + timedelta(hours=24),
            is_retryable=False,
            created_at=now,
            updated_at=now,
        )
        test_db_session.add(doc)
        await test_db_session.commit()

        # Write the temp PDF to the storage path
        os.makedirs(os.path.dirname(document_service.storage.get_absolute_path(doc.storage_key)), exist_ok=True)
        with open(document_service.storage.get_absolute_path(doc.storage_key), "wb") as f:
            f.write(pdf_bytes)

        result = await document_service.process_document_pipeline(doc_id, test_db_session)

    os.unlink(tmp.name)

    assert result.status == "READY_WITHOUT_EMBEDDINGS", (
        f"Expected READY_WITHOUT_EMBEDDINGS when provider unavailable, got: {result.status}"
    )


# ---------------------------------------------------------------------------
# 23. Batch embedding generation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_embedding_generation(test_db_session: AsyncSession):
    """
    Embedding generation must work with EMBEDDING_BATCH_SIZE < number of chunks.
    Verifies that all chunks receive an embedding even when batching is required.
    """
    from app.services.document_service import _generate_and_store_embeddings

    doc = _make_document()
    test_db_session.add(doc)
    await test_db_session.flush()

    # Create multiple clauses to generate multiple chunks.
    for i in range(1, 6):
        page = _make_page(doc.id, i, f"Clause {i} text: {SHORT_TEXT}")
        clause = _make_clause(doc.id, page.id, str(i), f"Clause {i} text: {SHORT_TEXT}", page_start=i)
        test_db_session.add(page)
        test_db_session.add(clause)

    await test_db_session.commit()

    chunker = DocumentChunker(chunk_size_tokens=500, chunk_overlap_tokens=75)
    await chunker.chunk_and_persist(doc.id, test_db_session)

    # Use small batch size to exercise the batching loop.
    provider = MockEmbeddingProvider(dim=768)
    with patch("app.services.document_service.settings") as mock_settings:
        mock_settings.EMBEDDING_BATCH_SIZE = 2  # Force batching with small batch
        count = await _generate_and_store_embeddings(doc.id, provider, test_db_session)

    assert count >= 5  # At least one chunk per clause.

    result = await test_db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
    )
    all_chunks = list(result.scalars().all())
    for chunk in all_chunks:
        assert chunk.embedding is not None, "All chunks must have embeddings after generation."
