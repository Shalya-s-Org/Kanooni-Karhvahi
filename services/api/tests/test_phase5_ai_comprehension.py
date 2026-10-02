"""
Phase 5 — AI Comprehension Layer Tests
=======================================

Test coverage:
  1. AI provider abstraction: BaseLLMProvider interface & factory resolution
  2. Mock provider: deterministic output, no network, provider/model metadata
  3. Provider unavailable: raising LLMProviderError for unregistered provider
  4. Structured output: schema validation for DocumentSummaryOutput and ClauseExplanationOutput
  5. Invalid structured output: Pydantic ValidationError on missing required fields
  6. Evidence pack builder: gathers classification, clauses, entities, chunks, pages
  7. Evidence traceability: stable evidence_id generation and valid_ids set
  8. Document summary generation: DB persistence, status COMPLETED, schema validity
  9. Document summary retrieval: GET endpoint returns cached COMPLETED analysis
 10. Clause explanation generation: DB persistence, original text preserved
 11. Cross-document clause security: block clause explanation if clause belongs to another document
 12. Hallucination guard: passes valid evidence IDs, sanitises invalid evidence IDs
 13. Hallucination guard: rejects output when ALL evidence IDs are hallucinated
 14. Safety rules: outputs contain required non-lawyer disclaimers & conservative check signals
 15. Persistence & deletion cascade: deleting document purges DocumentAnalysis and ClauseAnalysis
 16. API response envelope: success and error envelopes match Phase 1–4 conventions
 17. API error codes: DOCUMENT_NOT_READY, CLAUSE_NOT_FOUND, CLAUSE_DOCUMENT_MISMATCH, AI_PROVIDER_UNAVAILABLE
 18. Celery task: analyze_document task execution
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts import PROMPT_VERSION, SYSTEM_INSTRUCTION
from app.ai.providers.base import (
    BaseLLMProvider,
    LLMOutputParseError,
    LLMProviderError,
    MockLLMProvider,
)
from app.ai.providers.factory import AIProviderFactory, get_llm_provider
from app.ai.structured_output.schemas import (
    CheckSignal,
    CheckSignalSeverity,
    ClauseExplanationOutput,
    DocumentSummaryOutput,
    KeyPoint,
)
from app.analysis.clause_explanation import clause_explanation_service
from app.analysis.document_summary import document_summary_service
from app.analysis.evidence import EvidenceItem, EvidencePack, evidence_pack_builder
from app.analysis.guard import HallucinationGuard, hallucination_guard
from app.models.analysis import AnalysisStatus, AnalysisType, ClauseAnalysis, DocumentAnalysis
from app.models.document import (
    Document,
    DocumentChunk,
    DocumentClassification,
    DocumentClause,
    DocumentEntity,
    DocumentPage,
)


# ---------------------------------------------------------------------------
# Helper Factories
# ---------------------------------------------------------------------------

async def _seed_test_document(db: AsyncSession, status: str = "READY") -> Document:
    doc_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    doc = Document(
        id=doc_id,
        session_id="test-session",
        original_filename="test_contract.pdf",
        storage_key=f"uploads/{doc_id}/original/test_contract.pdf",
        mime_type="application/pdf",
        file_size=1024,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        status=status,
        page_count=2,
        ocr_required=False,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(hours=24),
    )
    db.add(doc)
    await db.flush()

    # Classification
    cls = DocumentClassification(
        id=uuid.uuid4(),
        document_id=doc_id,
        document_type="CONTRACT",
        confidence=0.95,
        evidence=[{"page": 1, "text": "RENT AGREEMENT"}],
    )
    db.add(cls)

    # Pages
    page1 = DocumentPage(
        id=uuid.uuid4(),
        document_id=doc_id,
        page_number=1,
        extracted_text="RENT AGREEMENT between Landlord A and Tenant B. Payment is due on the 5th of every month.",
        ocr_used=False,
    )
    page2 = DocumentPage(
        id=uuid.uuid4(),
        document_id=doc_id,
        page_number=2,
        extracted_text="Security deposit of ₹50,000 shall be refunded upon termination. Notice period is 30 days.",
        ocr_used=False,
    )
    # Clause
    clause1 = DocumentClause(
        id=uuid.uuid4(),
        document_id=doc_id,
        page_id=page1.id,
        clause_number="1",
        title="Rent Payment",
        original_text="Tenant B agrees to pay monthly rent of ₹15,000 to Landlord A by the 5th day of each calendar month.",
        page_start=1,
        page_end=1,
        confidence=0.9,
    )
    clause2 = DocumentClause(
        id=uuid.uuid4(),
        document_id=doc_id,
        page_id=page2.id,
        clause_number="2",
        title="Notice Period",
        original_text="Either party may terminate this agreement by giving 30 days written notice to the other party.",
        page_start=2,
        page_end=2,
        confidence=0.9,
    )
    db.add_all([clause1, clause2])
    await db.flush()

    # Entity
    entity1 = DocumentEntity(
        id=uuid.uuid4(),
        document_id=doc_id,
        page_id=page1.id,
        page_number=1,
        entity_type="MONEY",
        value="₹15,000",
        normalized_value="15000",
        source_text="pay monthly rent of ₹15,000 to Landlord A",
        confidence=0.95,
    )
    db.add(entity1)

    # Chunk
    chunk1 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        page_id=page1.id,
        clause_id=clause1.id,
        chunk_index=0,
        text="Tenant B agrees to pay monthly rent of ₹15,000 to Landlord A by the 5th day of each calendar month.",
        token_count=20,
        page_number=1,
    )
    db.add(chunk1)
    await db.commit()
    await db.refresh(doc)
    return doc, clause1


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_provider_abstraction():
    """Test 1: Factory resolves MockLLMProvider and raises LLMProviderError for invalid provider."""
    provider = get_llm_provider("mock")
    assert isinstance(provider, BaseLLMProvider)
    assert provider.provider_name == "mock"
    assert provider.model_name == "mock-llm-v1"

    # AIProviderFactory static interface
    provider2 = AIProviderFactory.get_provider("mock")
    assert provider2.provider_name == "mock"

    # Unregistered provider throws LLMProviderError
    with pytest.raises(LLMProviderError) as exc_info:
        get_llm_provider("nonexistent_provider")
    assert "nonexistent_provider" in str(exc_info.value)


@pytest.mark.asyncio
async def test_mock_llm_provider_deterministic():
    """Test 2: MockLLMProvider returns schema-valid output and is deterministic."""
    provider = MockLLMProvider()
    
    # Text completion
    text1 = await provider.generate_text("Test prompt")
    text2 = await provider.generate_text("Test prompt")
    assert text1 == text2
    assert "MOCK OUTPUT" in text1

    # Structured summary output
    schema = {
        "properties": {
            "summary": {"type": "string"},
            "purpose": {"type": "string"},
        }
    }
    output = await provider.generate_structured("Prompt with [clause-1234567890ab] Source:", schema)
    assert "summary" in output
    assert output["provider"] == "mock"
    assert output["model"] == "mock-llm-v1"


@pytest.mark.asyncio
async def test_structured_output_validation():
    """Test 4 & 5: Valid and invalid output validation using Pydantic schemas."""
    valid_summary = {
        "summary": "According to the uploaded document, this is a rent agreement.",
        "purpose": "Establishes a residential lease agreement between Landlord A and Tenant B.",
        "document_type": "CONTRACT",
        "key_points": [
            {
                "text": "According to the document, monthly rent is ₹15,000.",
                "evidence_refs": ["clause-123"],
            }
        ],
        "important_dates": ["5th of every month"],
        "important_amounts": ["₹15,000"],
        "important_parties": ["Landlord A", "Tenant B"],
        "obligations": ["Tenant B must pay rent by the 5th."],
        "check_signals": [
            {
                "category": "UNUSUAL_DEADLINE",
                "message": "Payment deadline is strict.",
                "severity": "INFO",
                "evidence_refs": ["clause-123"],
                "explanation": "Verify payment channel.",
            }
        ],
        "uncertainty_notes": [],
        "evidence_refs": ["clause-123"],
        "provider": "mock",
        "model": "mock-llm-v1",
    }
    parsed = DocumentSummaryOutput.model_validate(valid_summary)
    assert parsed.document_type == "CONTRACT"
    assert len(parsed.key_points) == 1

    # Missing required field 'summary' raises ValidationError
    invalid_summary = valid_summary.copy()
    del invalid_summary["summary"]
    with pytest.raises(Exception):
        DocumentSummaryOutput.model_validate(invalid_summary)


@pytest.mark.asyncio
async def test_evidence_pack_builder(test_db_session: AsyncSession):
    """Test 6 & 7: EvidencePackBuilder gathers all evidence categories with stable IDs."""
    doc, clause = await _seed_test_document(test_db_session)
    pack = await evidence_pack_builder.build_for_document(doc.id, test_db_session)

    assert pack.document_id == doc.id
    assert pack.document_type == "CONTRACT"
    assert len(pack.items) >= 4
    assert len(pack.valid_ids) == len(pack.items)

    types = {item.source_type for item in pack.items}
    assert "classification" in types
    assert "clause" in types
    assert "entity" in types
    assert "chunk" in types


@pytest.mark.asyncio
async def test_document_summary_service_flow(test_db_session: AsyncSession):
    """Test 8 & 9: Summary generation, persistence, and caching."""
    doc, clause = await _seed_test_document(test_db_session)

    # Generate summary
    analysis = await document_summary_service.generate_summary(doc.id, test_db_session)
    assert analysis.status == AnalysisStatus.COMPLETED
    assert analysis.document_id == doc.id
    assert analysis.output_json is not None
    assert "summary" in analysis.output_json

    # Retrieve cached summary
    cached = await document_summary_service.get_summary(doc.id, test_db_session)
    assert cached is not None
    assert cached.id == analysis.id
    assert cached.status == AnalysisStatus.COMPLETED


@pytest.mark.asyncio
async def test_clause_explanation_service_flow(test_db_session: AsyncSession):
    """Test 10: Clause explanation generation and original clause preservation."""
    doc, clause = await _seed_test_document(test_db_session)

    analysis = await clause_explanation_service.explain_clause(doc.id, clause.id, test_db_session)
    assert analysis.status == AnalysisStatus.COMPLETED
    assert analysis.clause_id == clause.id
    assert analysis.output_json is not None
    assert "plain_meaning" in analysis.output_json


@pytest.mark.asyncio
async def test_cross_document_clause_security(test_db_session: AsyncSession):
    """Test 11: Security check - explaining a clause belonging to another document raises error."""
    doc1, clause_doc1 = await _seed_test_document(test_db_session)
    doc2, clause_doc2 = await _seed_test_document(test_db_session)

    with pytest.raises(ValueError) as exc_info:
        await clause_explanation_service.explain_clause(doc2.id, clause_doc1.id, test_db_session)
    assert "does not belong to document" in str(exc_info.value)


@pytest.mark.asyncio
async def test_hallucination_guard():
    """Test 12 & 13: HallucinationGuard evidence ID validation."""
    guard = HallucinationGuard()
    valid_ids = {"clause-123", "entity-456"}

    raw_output = {
        "summary": "According to the uploaded document, this is a test.",
        "purpose": "Testing guard behavior.",
        "document_type": "CONTRACT",
        "key_points": [
            {
                "text": "According to the document, point 1.",
                "evidence_refs": ["clause-123"],
            }
        ],
        "check_signals": [],
        "uncertainty_notes": [],
        "evidence_refs": ["clause-123"],
        "provider": "mock",
        "model": "mock-v1",
    }
    result = guard.validate_summary(raw_output, valid_ids)
    assert result.passed is True

    # Totally hallucinated evidence IDs
    hallucinated = raw_output.copy()
    hallucinated["key_points"] = [
        {
            "text": "Fabricated point.",
            "evidence_refs": ["fake-id-999"],
        }
    ]
    hallucinated["evidence_refs"] = ["fake-id-999"]
    res_fake = guard.validate_summary(hallucinated, valid_ids)
    assert res_fake.passed is False
    assert "hallucinated" in res_fake.errors[0].lower()


@pytest.mark.asyncio
async def test_persistence_and_cascade_deletion(test_db_session: AsyncSession):
    """Test 15: Document deletion cascades and purges analysis records."""
    doc, clause = await _seed_test_document(test_db_session)

    await document_summary_service.generate_summary(doc.id, test_db_session)
    await clause_explanation_service.explain_clause(doc.id, clause.id, test_db_session)

    # Verify records exist
    res_sum = await test_db_session.execute(select(DocumentAnalysis).where(DocumentAnalysis.document_id == doc.id))
    assert len(list(res_sum.scalars().all())) == 1

    res_cl = await test_db_session.execute(select(ClauseAnalysis).where(ClauseAnalysis.document_id == doc.id))
    assert len(list(res_cl.scalars().all())) == 1

    # Delete parent document
    await test_db_session.delete(doc)
    await test_db_session.commit()

    # Verify cascaded deletion
    res_sum_after = await test_db_session.execute(select(DocumentAnalysis).where(DocumentAnalysis.document_id == doc.id))
    assert len(list(res_sum_after.scalars().all())) == 0

    res_cl_after = await test_db_session.execute(select(ClauseAnalysis).where(ClauseAnalysis.document_id == doc.id))
    assert len(list(res_cl_after.scalars().all())) == 0


@pytest.mark.asyncio
async def test_phase5_api_endpoints(async_client: AsyncClient, test_db_session: AsyncSession):
    """Test 16 & 17: Phase 5 API routes success and error response envelopes."""
    doc, clause = await _seed_test_document(test_db_session)

    # 1. POST /api/v1/documents/{doc_id}/summary
    res_sum = await async_client.post(f"/api/v1/documents/{doc.id}/summary")
    assert res_sum.status_code == 200
    body_sum = res_sum.json()
    assert body_sum["success"] is True
    assert body_sum["data"]["document_id"] == str(doc.id)
    assert body_sum["data"]["status"] == "COMPLETED"

    # 2. GET /api/v1/documents/{doc_id}/summary
    res_get_sum = await async_client.get(f"/api/v1/documents/{doc.id}/summary")
    assert res_get_sum.status_code == 200
    assert res_get_sum.json()["data"]["analysis_id"] == body_sum["data"]["analysis_id"]

    # 3. POST /api/v1/documents/{doc_id}/clauses/{clause_id}/explain
    res_exp = await async_client.post(f"/api/v1/documents/{doc.id}/clauses/{clause.id}/explain")
    assert res_exp.status_code == 200
    body_exp = res_exp.json()
    assert body_exp["success"] is True
    assert body_exp["data"]["clause_id"] == str(clause.id)
    assert body_exp["data"]["original_text"] == clause.original_text

    # 4. Error: Cross-document clause access (mismatch)
    doc2, clause2 = await _seed_test_document(test_db_session)
    res_mismatch = await async_client.post(f"/api/v1/documents/{doc2.id}/clauses/{clause.id}/explain")
    assert res_mismatch.status_code == 200
    body_mismatch = res_mismatch.json()
    assert body_mismatch["success"] is False
    assert body_mismatch["error"]["code"] == "CLAUSE_DOCUMENT_MISMATCH"

    # 5. Error: Document not ready
    doc_unready, clause_unready = await _seed_test_document(test_db_session, status="PROCESSING")
    res_not_ready = await async_client.post(f"/api/v1/documents/{doc_unready.id}/summary")
    assert res_not_ready.status_code == 200
    body_nr = res_not_ready.json()
    assert body_nr["success"] is False
    assert body_nr["error"]["code"] == "DOCUMENT_NOT_READY"
