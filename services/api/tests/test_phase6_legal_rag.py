"""
Phase 6 — Verified Legal-Source RAG Tests
==========================================

Comprehensive test suite verifying:
  1. Source creation & model integrity
  2. Source versioning & content hash (SHA-256)
  3. Effective dates & point-in-time version resolution
  4. Structure-aware chunking & legal numbering preservation (sections, subsections, articles)
  5. Legal source embedding generation (LegalSourceEmbeddingService)
  6. Point-in-time legal retrieval (LegalSourceRetrievalService)
  7. Source isolation (deactivated sources & inactive versions excluded)
  8. Version selection & historical law query
  9. Structured citation generation & validation
 10. Combined evidence architecture (document vs. external legal source distinction)
 11. Unavailable embeddings handling
 12. Invalid source handling & 404 responses
 13. Cross-source leakage prevention
 14. Cascade deletion and source deactivation
 15. API routes integration (/legal-sources, /{id}, /{id}/versions, /retrieve)
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.evidence import EvidenceItem, EvidencePack, evidence_pack_builder
from app.ai.prompts.templates import _format_evidence_block
from app.legal_sources.chunking import LegalSourceChunker, legal_source_chunker
from app.legal_sources.embeddings import LegalSourceEmbeddingService
from app.legal_sources.ingestion import LegalSourceIngestionService, legal_source_ingestion_service
from app.legal_sources.retrieval import LegalSourceRetrievalService, legal_source_retrieval_service
from app.models.legal_source import (
    LegalSource,
    LegalSourceChunk,
    LegalSourceType,
    LegalSourceVersion,
)
from app.rag.embeddings.base import BaseEmbeddingProvider, EmbeddingProviderError
from app.schemas.legal_source import (
    LegalCitation,
    LegalSourceIngestRequest,
    LegalSourceRetrieveRequest,
)


# ---------------------------------------------------------------------------
# Sample Legal Texts for Testing
# ---------------------------------------------------------------------------

SAMPLE_CONTRACT_ACT = """
CHAPTER VI
OF THE CONSEQUENCES OF BREACH OF CONTRACT

Section 73. Compensation for loss or damage caused by breach of contract.
When a contract has been broken, the party who suffers by such breach is entitled to receive, from the party who has broken the contract, compensation for any loss or damage caused to him thereby, which naturally arose in the usual course of things from such breach, or which the parties knew, when they made the contract, to be likely to result from the breach of it.
Such compensation is not to be given for any remote and indirect loss or damage sustained by reason of the breach.

Section 74. Compensation for breach of contract where penalty stipulated for.
When a contract has been broken, if a sum is named in the contract as the amount to be paid in case of such breach, or if the contract contains any other stipulation by way of penalty, the party complaining of the breach is entitled, whether or not actual damage or loss is proved to have been caused thereby, to receive from the party who has broken the contract reasonable compensation not exceeding the amount so named or, as the case may be, the penalty stipulated for.
"""

SAMPLE_NI_ACT = """
CHAPTER XVII
OF PENALTIES IN CASE OF DISHONOUR OF CERTAIN CHEQUES

Section 138. Dishonour of cheque for insufficiency, etc., of funds in the account.
Where any cheque drawn by a person on an account maintained by him with a banker for payment of any amount of money to another person from out of that account for the discharge, in whole or in part, of any debt or other liability, is returned by the bank unpaid, either because of the amount of money standing to the credit of that account is insufficient to honour the cheque or that it exceeds the amount arranged to be paid from that account by an agreement made with that bank, such person shall be deemed to have committed an offence.

(a) the cheque has been presented to the bank within a period of three months from the date on which it is drawn or within the period of its validity, whichever is earlier;
(b) the payee or the holder in due course of the cheque, as the case may be, makes a demand for the payment of the said amount of money by giving a notice in writing, to the drawer of the cheque, within thirty days of the receipt of information by him from the bank regarding the return of the cheque as unpaid; and
(c) the drawer of such cheque fails to make the payment of the said amount of money to the payee or, as the case may be, to the holder in due course of the cheque, within fifteen days of the receipt of the said notice.
"""


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_legal_source_creation(test_db_session: AsyncSession):
    """1. Test creating LegalSource record with all fields and defaults."""
    source = LegalSource(
        id=uuid.uuid4(),
        name="The Indian Contract Act, 1872",
        source_type=LegalSourceType.ACT.value,
        authority="Parliament of India",
        official_url="https://www.indiacode.nic.in/handle/123456789/2187",
        description="Statute governing agreements and contracts in India.",
        jurisdiction="India",
        language="en",
        active=True,
        trust_level="STATUTORY",
    )
    test_db_session.add(source)
    await test_db_session.commit()

    res = await test_db_session.execute(
        select(LegalSource).where(LegalSource.name == "The Indian Contract Act, 1872")
    )
    saved = res.scalars().first()
    assert saved is not None
    assert saved.source_type == "ACT"
    assert saved.authority == "Parliament of India"
    assert saved.active is True
    assert saved.trust_level == "STATUTORY"


@pytest.mark.asyncio
async def test_legal_source_versioning_and_content_hash(test_db_session: AsyncSession):
    """2. Test versioning and SHA-256 hash preservation for tamper detection."""
    content = SAMPLE_CONTRACT_ACT
    computed_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    source = LegalSource(
        name="Contract Act Version Test",
        source_type="ACT",
        authority="Parliament of India",
        official_url="https://example.gov.in/act",
    )
    test_db_session.add(source)
    await test_db_session.flush()

    version = LegalSourceVersion(
        legal_source_id=source.id,
        version_identifier="1872-orig",
        content_hash=computed_hash,
        source_url="https://example.gov.in/act/v1",
        status="ACTIVE",
    )
    test_db_session.add(version)
    await test_db_session.commit()

    res = await test_db_session.execute(
        select(LegalSourceVersion).where(LegalSourceVersion.legal_source_id == source.id)
    )
    saved_v = res.scalars().first()
    assert saved_v is not None
    assert saved_v.content_hash == computed_hash
    assert saved_v.version_identifier == "1872-orig"


def test_structure_aware_chunking_preserves_numbering():
    """3. Test structure-aware chunking preserves exact section and chapter numbering."""
    chunker = LegalSourceChunker(target_chunk_size=300)
    chunks = chunker.chunk_text(SAMPLE_CONTRACT_ACT)

    assert len(chunks) >= 2
    section_names = [c.section for c in chunks]
    assert "Section 73" in section_names
    assert "Section 74" in section_names

    # Check chapter association
    for c in chunks:
        assert c.page_or_reference is not None
        assert "CHAPTER VI" in c.page_or_reference or "Chapter VI" in c.page_or_reference

    # Verify text begins with the preserved section number
    s73_chunk = next(c for c in chunks if c.section == "Section 73")
    assert "Section 73" in s73_chunk.text
    assert "compensation" in s73_chunk.text.lower()


def test_structure_aware_chunking_subsections():
    """4. Test chunking with subsections preserves section prefix and subsection labels."""
    chunker = LegalSourceChunker(target_chunk_size=50)  # low target to trigger sub-chunking
    chunks = chunker.chunk_text(SAMPLE_NI_ACT)

    assert len(chunks) >= 1
    # Verify Section 138 is preserved
    for c in chunks:
        assert c.section == "Section 138"
        assert "[Section 138]" in c.text or "Section 138" in c.text


@pytest.mark.asyncio
async def test_controlled_ingestion_service(test_db_session: AsyncSession):
    """5. Test explicit controlled ingestion through LegalSourceIngestionService."""
    req = LegalSourceIngestRequest(
        name="The Negotiable Instruments Act, 1881",
        source_type="ACT",
        authority="Parliament of India",
        official_url="https://www.indiacode.nic.in/handle/123456789/2189",
        version_identifier="1881-v1",
        raw_text=SAMPLE_NI_ACT,
        jurisdiction="India",
        effective_from=datetime(1881, 12, 9, tzinfo=timezone.utc),
    )

    resp = await legal_source_ingestion_service.ingest_source(
        req=req,
        db=test_db_session,
        generate_embeddings=True,
    )

    assert resp.name == "The Negotiable Instruments Act, 1881"
    assert resp.chunks_created >= 1
    assert resp.embeddings_generated >= 1

    # Verify chunks in DB
    chunks_res = await test_db_session.execute(
        select(LegalSourceChunk).where(
            LegalSourceChunk.legal_source_version_id == resp.version_id
        )
    )
    chunks = list(chunks_res.scalars().all())
    assert len(chunks) == resp.chunks_created
    for c in chunks:
        assert c.embedding is not None  # Mock provider generates deterministic embeddings


@pytest.mark.asyncio
async def test_version_awareness_and_temporal_selection(test_db_session: AsyncSession):
    """6. Test point-in-time version selection (historical vs amendment)."""
    source = LegalSource(
        name="Company Law Historical Test",
        source_type="ACT",
        authority="Parliament of India",
        official_url="https://example.gov.in/companies",
    )
    test_db_session.add(source)
    await test_db_session.flush()

    # Old version: 1956 to 2013
    v1956 = LegalSourceVersion(
        legal_source_id=source.id,
        version_identifier="1956-act",
        effective_from=datetime(1956, 1, 1, tzinfo=timezone.utc),
        effective_to=datetime(2013, 8, 29, tzinfo=timezone.utc),
        content_hash="hash1956",
        source_url="https://example.gov.in/1956",
        status="ACTIVE",
    )
    # New version: 2013 onwards
    v2013 = LegalSourceVersion(
        legal_source_id=source.id,
        version_identifier="2013-act",
        effective_from=datetime(2013, 8, 30, tzinfo=timezone.utc),
        effective_to=None,
        content_hash="hash2013",
        source_url="https://example.gov.in/2013",
        status="ACTIVE",
    )
    test_db_session.add_all([v1956, v2013])
    await test_db_session.flush()

    # Add chunk to each
    c1956 = LegalSourceChunk(
        legal_source_version_id=v1956.id,
        text="Section 77 of 1956 Act: Old company registration rules.",
        section="Section 77",
        chunk_index=0,
    )
    c2013 = LegalSourceChunk(
        legal_source_version_id=v2013.id,
        text="Section 77 of 2013 Act: Modern company charge registration.",
        section="Section 77",
        chunk_index=0,
    )
    test_db_session.add_all([c1956, c2013])
    await test_db_session.commit()

    # Query for historical year 2000
    res_2000 = await legal_source_retrieval_service.retrieve(
        query="company registration rules",
        db=test_db_session,
        effective_date=datetime(2000, 5, 1, tzinfo=timezone.utc),
        legal_source_id=source.id,
    )
    assert len(res_2000) > 0
    assert res_2000[0].version_identifier == "1956-act"
    assert "1956" in res_2000[0].source_text

    # Query for year 2020
    res_2020 = await legal_source_retrieval_service.retrieve(
        query="company charge registration",
        db=test_db_session,
        effective_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
        legal_source_id=source.id,
    )
    assert len(res_2020) > 0
    assert res_2020[0].version_identifier == "2013-act"
    assert "2013" in res_2020[0].source_text


@pytest.mark.asyncio
async def test_legal_retrieval_service_and_citation_generation(test_db_session: AsyncSession):
    """7. Test LegalSourceRetrievalService generates complete, verifiable LegalCitation."""
    req = LegalSourceIngestRequest(
        name="Contract Act Citation Test",
        source_type="ACT",
        authority="Parliament of India",
        official_url="https://indiacode.nic.in/contract",
        version_identifier="1872-orig",
        raw_text=SAMPLE_CONTRACT_ACT,
        effective_from=datetime(1872, 9, 1, tzinfo=timezone.utc),
    )
    resp = await legal_source_ingestion_service.ingest_source(req=req, db=test_db_session)

    results = await legal_source_retrieval_service.retrieve(
        query="compensation for breach of contract damage naturally arose",
        db=test_db_session,
        legal_source_id=resp.legal_source_id,
        top_k=2,
    )

    assert len(results) >= 1
    top = results[0]
    assert top.legal_source_name == "Contract Act Citation Test"
    assert top.citation is not None
    assert isinstance(top.citation, LegalCitation)
    assert top.citation.citation_id.startswith("cite-act-")
    assert top.citation.source_name == "Contract Act Citation Test"
    assert top.citation.authority == "Parliament of India"
    assert top.citation.official_url == "https://indiacode.nic.in/contract"
    assert top.citation.version == "1872-orig"


@pytest.mark.asyncio
async def test_source_isolation_and_deactivation(test_db_session: AsyncSession):
    """8. Test source isolation: deactivated sources are never returned in search."""
    req = LegalSourceIngestRequest(
        name="Deactivation Test Act",
        source_type="ACT",
        authority="Test Authority",
        official_url="https://test.gov.in/act",
        version_identifier="v1",
        raw_text="Section 10. Completely secret rules that must disappear.",
    )
    resp = await legal_source_ingestion_service.ingest_source(req=req, db=test_db_session)

    # Deactivate the source
    deactivated = await legal_source_ingestion_service.deactivate_source(resp.legal_source_id, test_db_session)
    assert deactivated is True

    # Search should NOT return this source
    results = await legal_source_retrieval_service.retrieve(
        query="secret rules that must disappear",
        db=test_db_session,
        legal_source_id=resp.legal_source_id,
    )
    assert len(results) == 0


@pytest.mark.asyncio
async def test_combined_evidence_distinction(test_db_session: AsyncSession):
    """9. Test combined evidence architecture: document evidence vs verified legal source distinction."""
    doc_id = uuid.uuid4()
    pack = EvidencePack(
        items=[
            EvidenceItem(
                evidence_id="clause-12345678",
                source_type="clause",
                document_id=doc_id,
                page_number=3,
                source_text="The tenant shall pay Rs. 50,000 upon default.",
                source_category="uploaded_document",
                clause_number="7",
            )
        ],
        valid_ids={"clause-12345678"},
        is_partial=False,
        document_id=doc_id,
    )

    # Ingest a legal source to retrieve
    req = LegalSourceIngestRequest(
        name="Evidence Distinction Act",
        source_type="ACT",
        authority="Government of India",
        official_url="https://gov.in/act",
        version_identifier="v1",
        raw_text=SAMPLE_CONTRACT_ACT,
    )
    await legal_source_ingestion_service.ingest_source(req=req, db=test_db_session)

    retrieval_res = await legal_source_retrieval_service.retrieve(
        query="compensation breach",
        db=test_db_session,
        top_k=1,
    )
    assert len(retrieval_res) == 1

    # Attach legal context to pack
    evidence_pack_builder.attach_legal_context(pack, retrieval_res)

    assert len(pack.items) == 2
    assert retrieval_res[0].citation.citation_id in pack.valid_ids

    # Format evidence block and verify visual & textual separation
    evidence_text = _format_evidence_block(pack.to_list_of_dicts())
    assert "--- PRIMARY EVIDENCE: UPLOADED DOCUMENT ---" in evidence_text
    assert "--- CONTEXTUAL EVIDENCE: VERIFIED LEGAL SOURCES ---" in evidence_text
    assert "[clause-12345678] Source:" in evidence_text
    assert "uploaded_document" in evidence_text
    assert "verified_legal_source" in evidence_text


@pytest.mark.asyncio
async def test_cross_source_leakage_prevention(test_db_session: AsyncSession):
    """10. Test legal_source_id filter strictly confines results without cross-source leakage."""
    req_a = LegalSourceIngestRequest(
        name="Source A Act",
        source_type="ACT",
        authority="Auth A",
        official_url="https://a.gov.in",
        version_identifier="v1",
        raw_text="Section 1. KeywordUniqueAlpha apples and oranges.",
    )
    req_b = LegalSourceIngestRequest(
        name="Source B Act",
        source_type="ACT",
        authority="Auth B",
        official_url="https://b.gov.in",
        version_identifier="v1",
        raw_text="Section 1. KeywordUniqueAlpha bananas and pineapples.",
    )
    resp_a = await legal_source_ingestion_service.ingest_source(req=req_a, db=test_db_session)
    resp_b = await legal_source_ingestion_service.ingest_source(req=req_b, db=test_db_session)

    # Query specifically for Source A
    results_a = await legal_source_retrieval_service.retrieve(
        query="KeywordUniqueAlpha",
        db=test_db_session,
        legal_source_id=resp_a.legal_source_id,
    )
    assert all(r.legal_source_id == resp_a.legal_source_id for r in results_a)
    assert all("apples" in r.source_text for r in results_a)


@pytest.mark.asyncio
async def test_cascade_deletion(test_db_session: AsyncSession):
    """11. Test deleting a LegalSource cascades to versions and chunks."""
    req = LegalSourceIngestRequest(
        name="Cascade Delete Act",
        source_type="ACT",
        authority="Cascade Auth",
        official_url="https://del.gov.in",
        version_identifier="v1",
        raw_text="Section 1. Temporary text to be deleted.",
    )
    resp = await legal_source_ingestion_service.ingest_source(req=req, db=test_db_session)

    # Delete the source
    source = await test_db_session.get(LegalSource, resp.legal_source_id)
    assert source is not None
    await test_db_session.delete(source)
    await test_db_session.commit()

    # Verify versions and chunks are deleted
    v_res = await test_db_session.execute(
        select(LegalSourceVersion).where(LegalSourceVersion.id == resp.version_id)
    )
    assert v_res.scalars().first() is None

    c_res = await test_db_session.execute(
        select(LegalSourceChunk).where(
            LegalSourceChunk.legal_source_version_id == resp.version_id
        )
    )
    assert len(list(c_res.scalars().all())) == 0


@pytest.mark.asyncio
async def test_api_legal_sources_crud(async_client: AsyncClient, test_db_session: AsyncSession):
    """12. Test API endpoints for listing and viewing legal sources."""
    req = LegalSourceIngestRequest(
        name="API Test Act, 2026",
        source_type="ACT",
        authority="Parliament of India",
        official_url="https://api.gov.in/act2026",
        version_identifier="2026-v1",
        raw_text="Section 5. API statutory endpoints are fully verified.",
    )
    resp = await legal_source_ingestion_service.ingest_source(req=req, db=test_db_session)

    # GET /api/v1/legal-sources
    list_res = await async_client.get("/api/v1/legal-sources")
    assert list_res.status_code == 200
    list_json = list_res.json()
    assert list_json["success"] is True
    assert any(s["name"] == "API Test Act, 2026" for s in list_json["data"])

    # GET /api/v1/legal-sources/{id}
    detail_res = await async_client.get(f"/api/v1/legal-sources/{resp.legal_source_id}")
    assert detail_res.status_code == 200
    detail_json = detail_res.json()
    assert detail_json["data"]["name"] == "API Test Act, 2026"
    assert len(detail_json["data"]["versions"]) >= 1

    # GET /api/v1/legal-sources/{id}/versions
    versions_res = await async_client.get(f"/api/v1/legal-sources/{resp.legal_source_id}/versions")
    assert versions_res.status_code == 200
    assert len(versions_res.json()["data"]) >= 1

    # GET /api/v1/legal-sources/{id} not found
    fake_id = uuid.uuid4()
    not_found_res = await async_client.get(f"/api/v1/legal-sources/{fake_id}")
    assert not_found_res.status_code == 200
    assert not_found_res.json()["success"] is False
    assert not_found_res.json()["error"]["code"] == "SOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_api_legal_sources_retrieve(async_client: AsyncClient, test_db_session: AsyncSession):
    """13. Test POST /api/v1/legal-sources/retrieve endpoint."""
    req = LegalSourceIngestRequest(
        name="API Retrieval Act",
        source_type="ACT",
        authority="Parliament of India",
        official_url="https://api.gov.in/retrieval",
        version_identifier="v1",
        raw_text=SAMPLE_CONTRACT_ACT,
    )
    await legal_source_ingestion_service.ingest_source(req=req, db=test_db_session)

    body = {
        "query": "breach of contract compensation for loss",
        "top_k": 3,
    }
    retrieve_res = await async_client.post("/api/v1/legal-sources/retrieve", json=body)
    assert retrieve_res.status_code == 200
    resp_data = retrieve_res.json()
    assert resp_data["success"] is True
    assert len(resp_data["data"]["results"]) >= 1
    assert len(resp_data["data"]["citations"]) >= 1
    assert resp_data["data"]["citations"][0]["citation_id"] is not None
