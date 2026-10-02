"""
Evidence Pack Builder — Phase 5.

The EvidencePackBuilder gathers evidence BEFORE any LLM call so that:
  1. The LLM receives a bounded, traceable context window.
  2. Every claim the LLM makes can be validated against a known evidence set.
  3. The evidence snapshot is stored alongside the analysis for audit.

Evidence hierarchy (gathered in order of priority):
  1. DocumentClassification result
  2. All DocumentClause records (verbatim original_text)
  3. DocumentEntity records (dates, amounts, parties, authorities, etc.)
  4. DocumentChunk records (semantic chunks from page text)
  5. DocumentPage records (full extracted text, up to token budget)

Each evidence item receives a stable ``evidence_id`` derived from its
database UUID so the LLM can reference it in ``evidence_refs`` fields and
the guard can validate those references after generation.

Context budget
--------------
To avoid exceeding model context limits the builder:
  - Always includes the full classification and all clauses (primary evidence).
  - Includes all entities.
  - Includes chunks up to MAX_EVIDENCE_CHUNKS.
  - Stops adding page text once the rough token budget is reached.
  - Sets ``is_partial=True`` if evidence was truncated.

Token counting uses the same whitespace approximation as the chunker.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.document import (
    Document,
    DocumentChunk,
    DocumentClassification,
    DocumentClause,
    DocumentEntity,
    DocumentPage,
)

# Maximum number of chunk evidence items to include.
MAX_EVIDENCE_CHUNKS = 20
# Rough token budget for page text evidence (conservative).
MAX_PAGE_TOKEN_BUDGET = 3000
# Maximum evidence items total to prevent overly long prompts.
MAX_TOTAL_EVIDENCE = 60


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class EvidenceItem:
    """
    A single traceable evidence item submitted to the LLM.

    ``evidence_id`` is the stable reference that the LLM puts in
    ``evidence_refs`` fields and the hallucination guard validates.
    """
    evidence_id: str          # Stable identifier (UUID-based)
    source_type: str          # "clause" | "entity" | "chunk" | "classification" | "page"
    document_id: uuid.UUID
    page_number: int
    source_text: str          # Verbatim text from the document
    # Optional enrichment
    page_id: Optional[uuid.UUID] = None
    clause_id: Optional[uuid.UUID] = None
    chunk_id: Optional[uuid.UUID] = None
    clause_number: Optional[str] = None
    retrieval_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source_type": self.source_type,
            "document_id": str(self.document_id),
            "page_number": self.page_number,
            "source_text": self.source_text,
            "page_id": str(self.page_id) if self.page_id else None,
            "clause_id": str(self.clause_id) if self.clause_id else None,
            "chunk_id": str(self.chunk_id) if self.chunk_id else None,
            "clause_number": self.clause_number,
            "retrieval_score": self.retrieval_score,
        }


@dataclass
class EvidencePack:
    """
    Complete evidence collection for one LLM call.

    Attributes:
        items:        Ordered list of evidence items (primary first).
        valid_ids:    Set of all evidence_id strings for guard validation.
        is_partial:   True if evidence was truncated due to context limits.
        document_id:  The document being analysed.
        document_type: Classification result label.
        total_pages:  Page count of the document.
    """
    items: List[EvidenceItem]
    valid_ids: Set[str]
    is_partial: bool
    document_id: uuid.UUID
    document_type: str = "UNKNOWN"
    total_pages: int = 0

    def to_list_of_dicts(self) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in self.items]


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class EvidencePackBuilder:
    """
    Assembles a bounded, prioritised evidence pack for a document.

    Usage::

        builder = EvidencePackBuilder()
        pack = await builder.build_for_document(document_id, db)
        pack = await builder.build_for_clause(document_id, clause_id, db)
    """

    async def build_for_document(
        self,
        document_id: uuid.UUID,
        db: AsyncSession,
    ) -> EvidencePack:
        """
        Build evidence for a full document summary.

        Gathers: classification → clauses → entities → chunks → pages.
        """
        items: List[EvidenceItem] = []
        is_partial = False

        # Verify document exists.
        doc_result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = doc_result.scalars().first()
        if not doc:
            raise ValueError(f"Document {document_id} not found.")

        # 1. Classification
        cls_result = await db.execute(
            select(DocumentClassification).where(
                DocumentClassification.document_id == document_id
            )
        )
        classification = cls_result.scalars().first()
        doc_type = classification.document_type if classification else "UNKNOWN"

        if classification:
            for idx, ev in enumerate(classification.evidence or []):
                eid = f"cls-{str(document_id)[:8]}-{idx}"
                items.append(
                    EvidenceItem(
                        evidence_id=eid,
                        source_type="classification",
                        document_id=document_id,
                        page_number=ev.get("page", 1),
                        source_text=ev.get("text", ""),
                    )
                )

        # 2. Clauses — full verbatim text, always included.
        clauses_result = await db.execute(
            select(DocumentClause)
            .where(DocumentClause.document_id == document_id)
            .order_by(DocumentClause.page_start, DocumentClause.id)
        )
        clauses = list(clauses_result.scalars().all())

        for clause in clauses:
            eid = f"clause-{str(clause.id)[:12]}"
            items.append(
                EvidenceItem(
                    evidence_id=eid,
                    source_type="clause",
                    document_id=document_id,
                    page_number=clause.page_start,
                    source_text=clause.original_text,
                    page_id=clause.page_id,
                    clause_id=clause.id,
                    clause_number=clause.clause_number,
                )
            )

        # 3. Entities — dates, amounts, parties, authorities, etc.
        entities_result = await db.execute(
            select(DocumentEntity)
            .where(DocumentEntity.document_id == document_id)
            .order_by(DocumentEntity.page_number, DocumentEntity.entity_type)
        )
        entities = list(entities_result.scalars().all())

        for entity in entities:
            eid = f"entity-{str(entity.id)[:12]}"
            text = f"[{entity.entity_type}] {entity.value}"
            if entity.normalized_value:
                text += f" (normalized: {entity.normalized_value})"
            text += f" — Context: {entity.source_text[:200]}"
            items.append(
                EvidenceItem(
                    evidence_id=eid,
                    source_type="entity",
                    document_id=document_id,
                    page_number=entity.page_number,
                    source_text=text,
                    page_id=entity.page_id,
                )
            )

        # 4. Semantic chunks (up to MAX_EVIDENCE_CHUNKS).
        chunks_result = await db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
            .limit(MAX_EVIDENCE_CHUNKS)
        )
        chunks = list(chunks_result.scalars().all())

        for chunk in chunks:
            eid = f"chunk-{str(chunk.id)[:12]}"
            items.append(
                EvidenceItem(
                    evidence_id=eid,
                    source_type="chunk",
                    document_id=document_id,
                    page_number=chunk.page_number,
                    source_text=chunk.text,
                    page_id=chunk.page_id,
                    clause_id=chunk.clause_id,
                    chunk_id=chunk.id,
                    clause_number=(chunk.chunk_metadata or {}).get("clause_number"),
                )
            )

        # 5. Page text (remaining budget).
        pages_result = await db.execute(
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
        )
        pages = list(pages_result.scalars().all())

        token_budget = MAX_PAGE_TOKEN_BUDGET
        for page in pages:
            if not page.extracted_text or not page.extracted_text.strip():
                continue
            page_tokens = len(page.extracted_text.split())
            if token_budget <= 0:
                is_partial = True
                break
            text = page.extracted_text
            if page_tokens > token_budget:
                # Include only as many words as the budget allows.
                words = text.split()[:token_budget]
                text = " ".join(words) + " [truncated]"
                is_partial = True
            eid = f"page-{str(page.id)[:12]}"
            items.append(
                EvidenceItem(
                    evidence_id=eid,
                    source_type="page",
                    document_id=document_id,
                    page_number=page.page_number,
                    source_text=text,
                    page_id=page.id,
                )
            )
            token_budget -= min(page_tokens, token_budget)

        # Enforce hard cap.
        if len(items) > MAX_TOTAL_EVIDENCE:
            items = items[:MAX_TOTAL_EVIDENCE]
            is_partial = True

        valid_ids = {item.evidence_id for item in items}
        logger.info(
            "Evidence pack for document %s: %d items, partial=%s",
            document_id,
            len(items),
            is_partial,
        )

        return EvidencePack(
            items=items,
            valid_ids=valid_ids,
            is_partial=is_partial,
            document_id=document_id,
            document_type=doc_type,
            total_pages=doc.page_count,
        )

    async def build_for_clause(
        self,
        document_id: uuid.UUID,
        clause_id: uuid.UUID,
        db: AsyncSession,
    ) -> EvidencePack:
        """
        Build evidence for a single clause explanation.

        Gathers:
          - The clause itself (always primary)
          - Its semantic chunks
          - Entities on the same page
          - Adjacent clauses for context
        """
        items: List[EvidenceItem] = []

        # Verify document and clause exist and match.
        clause_result = await db.execute(
            select(DocumentClause).where(
                DocumentClause.id == clause_id,
                DocumentClause.document_id == document_id,
            )
        )
        clause = clause_result.scalars().first()
        if not clause:
            raise ValueError(
                f"Clause {clause_id} not found or does not belong to document {document_id}."
            )

        # Classification for document type context.
        cls_result = await db.execute(
            select(DocumentClassification).where(
                DocumentClassification.document_id == document_id
            )
        )
        classification = cls_result.scalars().first()
        doc_type = classification.document_type if classification else "UNKNOWN"

        # 1. The clause itself.
        eid = f"clause-{str(clause.id)[:12]}"
        items.append(
            EvidenceItem(
                evidence_id=eid,
                source_type="clause",
                document_id=document_id,
                page_number=clause.page_start,
                source_text=clause.original_text,
                page_id=clause.page_id,
                clause_id=clause.id,
                clause_number=clause.clause_number,
            )
        )

        # 2. Semantic chunks belonging to this clause.
        chunks_result = await db.execute(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.clause_id == clause_id,
            )
            .order_by(DocumentChunk.chunk_index)
        )
        for chunk in chunks_result.scalars().all():
            eid = f"chunk-{str(chunk.id)[:12]}"
            items.append(
                EvidenceItem(
                    evidence_id=eid,
                    source_type="chunk",
                    document_id=document_id,
                    page_number=chunk.page_number,
                    source_text=chunk.text,
                    page_id=chunk.page_id,
                    clause_id=chunk.clause_id,
                    chunk_id=chunk.id,
                )
            )

        # 3. Entities on the same page.
        entities_result = await db.execute(
            select(DocumentEntity).where(
                DocumentEntity.document_id == document_id,
                DocumentEntity.page_number == clause.page_start,
            )
        )
        for entity in entities_result.scalars().all():
            eid = f"entity-{str(entity.id)[:12]}"
            text = f"[{entity.entity_type}] {entity.value}"
            if entity.normalized_value:
                text += f" ({entity.normalized_value})"
            text += f" — {entity.source_text[:200]}"
            items.append(
                EvidenceItem(
                    evidence_id=eid,
                    source_type="entity",
                    document_id=document_id,
                    page_number=entity.page_number,
                    source_text=text,
                    page_id=entity.page_id,
                )
            )

        valid_ids = {item.evidence_id for item in items}
        return EvidencePack(
            items=items,
            valid_ids=valid_ids,
            is_partial=False,
            document_id=document_id,
            document_type=doc_type,
            total_pages=clause.page_end,
        )


# Module-level singleton.
evidence_pack_builder = EvidencePackBuilder()
