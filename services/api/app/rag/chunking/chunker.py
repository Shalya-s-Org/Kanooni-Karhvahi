"""
Clause-aware semantic chunker.

Chunking priority:
  1. Explicit clause boundaries  (each DocumentClause is the primary unit)
  2. Paragraph boundaries        (double-newline split within a clause)
  3. Sentence boundaries         (period/newline split within a paragraph)
  4. Character/token limit       (hard split of very long sentences)

A short clause that already fits within the configured chunk size is emitted
as exactly one chunk — it is never split unnecessarily.

A long clause is split by paragraphs, then sentences, then by character
limit — but every resulting chunk retains full traceability back to its
source clause, page, and document.

Configuration (all via environment variables / settings):
  CHUNK_SIZE_TOKENS    – target maximum tokens per chunk (default 500)
  CHUNK_OVERLAP_TOKENS – overlap between consecutive chunks within a clause
                         (default 75)

Token counting uses a simple word-boundary heuristic (split on whitespace).
The abstraction is designed so a proper BPE tokenizer can be substituted
later without changing the chunker's interface.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.logging import logger
from app.models.document import Document, DocumentChunk, DocumentClause, DocumentPage


# ---------------------------------------------------------------------------
# Tokenisation helper
# ---------------------------------------------------------------------------

def _count_tokens(text: str) -> int:
    """
    Approximate token count using whitespace splitting.

    This is intentionally simple.  It slightly over-counts compared to a BPE
    tokenizer (1 word ≈ 1–1.3 BPE tokens) which gives a conservative
    (smaller) chunk size — erring on the side of fitting within model limits.

    Replace this function with a real tokenizer (e.g. tiktoken) when
    available without adding it as a hard dependency.
    """
    return len(text.split())


# ---------------------------------------------------------------------------
# Sentence splitter
# ---------------------------------------------------------------------------

# Match sentence-ending punctuation followed by whitespace / line boundary.
_SENTENCE_RE = re.compile(
    r"(?<=[.!?؟।\n])[\s]+"  # Unicode-aware: includes Devanagari danda and Arabic question mark
)


def _split_sentences(text: str) -> List[str]:
    """Split *text* into sentences using punctuation boundaries."""
    parts = _SENTENCE_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ChunkMetadata:
    """
    Full traceability record for a single text chunk.

    Every chunk must be independently traceable back to:
      document → page → clause → original source text
    """
    document_id: uuid.UUID
    page_id: Optional[uuid.UUID]
    page_number: int
    clause_id: Optional[uuid.UUID]
    clause_number: Optional[str]
    chunk_index: int
    text: str
    token_count: int
    source_type: str = "uploaded_document"
    # Extra data stored in DocumentChunk.chunk_metadata JSON column.
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core chunker
# ---------------------------------------------------------------------------

class DocumentChunker:
    """
    Clause-aware semantic chunker.

    Public interface::

        chunker = DocumentChunker()
        chunks = await chunker.chunk_and_persist(document_id, db)
    """

    def __init__(
        self,
        chunk_size_tokens: Optional[int] = None,
        chunk_overlap_tokens: Optional[int] = None,
    ) -> None:
        # Allow constructor override for tests; otherwise read from settings.
        self._chunk_size = chunk_size_tokens
        self._chunk_overlap = chunk_overlap_tokens

    @property
    def chunk_size(self) -> int:
        return self._chunk_size if self._chunk_size is not None else settings.CHUNK_SIZE_TOKENS

    @property
    def chunk_overlap(self) -> int:
        return self._chunk_overlap if self._chunk_overlap is not None else settings.CHUNK_OVERLAP_TOKENS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chunk_and_persist(
        self,
        document_id: uuid.UUID,
        db: AsyncSession,
    ) -> List[DocumentChunk]:
        """
        Chunk all clauses (or pages if no clauses exist) for *document_id*,
        persist them to ``document_chunks``, and return the saved records.

        This method is idempotent: existing chunks for the document are
        deleted before the new set is inserted.
        """
        # Verify document exists.
        doc_result = await db.execute(select(Document).where(Document.id == document_id))
        doc = doc_result.scalars().first()
        if not doc:
            raise ValueError(f"Document {document_id} not found.")

        # Load all pages (needed for page_id lookup when clauses span pages).
        pages_result = await db.execute(
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
        )
        pages = list(pages_result.scalars().all())
        page_by_number = {p.page_number: p for p in pages}

        # Load all clauses for the document, ordered by page then position.
        clauses_result = await db.execute(
            select(DocumentClause)
            .where(DocumentClause.document_id == document_id)
            .order_by(DocumentClause.page_start, DocumentClause.id)
        )
        clauses = list(clauses_result.scalars().all())

        # Generate chunk metadata objects.
        if clauses:
            metas = self._chunk_from_clauses(document_id, clauses, page_by_number)
        else:
            # Fallback: no clauses detected — chunk directly from pages.
            logger.warning(
                "Document %s has no clauses; chunking directly from pages.", document_id
            )
            metas = self._chunk_from_pages(document_id, pages)

        # Idempotent: delete any previous chunks for this document.
        await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))

        now = datetime.now(timezone.utc)
        saved: List[DocumentChunk] = []

        for meta in metas:
            chunk = DocumentChunk(
                id=uuid.uuid4(),
                document_id=meta.document_id,
                page_id=meta.page_id,
                clause_id=meta.clause_id,
                chunk_index=meta.chunk_index,
                text=meta.text,
                token_count=meta.token_count,
                page_number=meta.page_number,
                chunk_metadata={
                    "clause_number": meta.clause_number,
                    "source_type": meta.source_type,
                    **meta.extra,
                },
                created_at=now,
                updated_at=now,
            )
            db.add(chunk)
            saved.append(chunk)

        await db.commit()
        logger.info(
            "Chunked document %s: %d clauses → %d chunks",
            document_id,
            len(clauses),
            len(saved),
        )
        return saved

    # ------------------------------------------------------------------
    # Internal chunking logic
    # ------------------------------------------------------------------

    def _chunk_from_clauses(
        self,
        document_id: uuid.UUID,
        clauses: List[DocumentClause],
        page_by_number: dict,
    ) -> List[ChunkMetadata]:
        """
        Produce ChunkMetadata list from a list of DocumentClause records.
        Each clause is the primary unit; long clauses are split further.
        """
        metas: List[ChunkMetadata] = []
        global_index = 0

        for clause in clauses:
            # Resolve page_id from page_start if not directly attached.
            page_id = clause.page_id
            if page_id is None and clause.page_start in page_by_number:
                page_id = page_by_number[clause.page_start].id

            clause_chunks = self._split_clause(
                text=clause.original_text,
                document_id=document_id,
                page_id=page_id,
                page_number=clause.page_start,
                clause_id=clause.id,
                clause_number=clause.clause_number,
                start_index=global_index,
            )
            metas.extend(clause_chunks)
            global_index += len(clause_chunks)

        return metas

    def _chunk_from_pages(
        self,
        document_id: uuid.UUID,
        pages: List[DocumentPage],
    ) -> List[ChunkMetadata]:
        """
        Fallback: produce chunks directly from page text when no clauses exist.
        """
        metas: List[ChunkMetadata] = []
        global_index = 0

        for page in pages:
            if not page.extracted_text or not page.extracted_text.strip():
                continue

            page_chunks = self._split_clause(
                text=page.extracted_text,
                document_id=document_id,
                page_id=page.id,
                page_number=page.page_number,
                clause_id=None,
                clause_number=None,
                start_index=global_index,
            )
            metas.extend(page_chunks)
            global_index += len(page_chunks)

        return metas

    def _split_clause(
        self,
        text: str,
        document_id: uuid.UUID,
        page_id: Optional[uuid.UUID],
        page_number: int,
        clause_id: Optional[uuid.UUID],
        clause_number: Optional[str],
        start_index: int,
    ) -> List[ChunkMetadata]:
        """
        Split a single clause's text into one or more ChunkMetadata objects.

        If the whole clause fits within ``chunk_size``, one chunk is produced.
        Otherwise the clause is split by paragraphs → sentences → hard-limit.
        An overlap of ``chunk_overlap`` tokens is maintained between adjacent
        chunks within the same clause.
        """
        text = text.strip()
        if not text:
            return []

        token_count = _count_tokens(text)

        # Short clause → single chunk, no splitting needed.
        if token_count <= self.chunk_size:
            return [
                ChunkMetadata(
                    document_id=document_id,
                    page_id=page_id,
                    page_number=page_number,
                    clause_id=clause_id,
                    clause_number=clause_number,
                    chunk_index=start_index,
                    text=text,
                    token_count=token_count,
                )
            ]

        # Long clause → split into segments with overlap.
        segments = self._build_segments(text)
        return self._merge_segments_into_chunks(
            segments=segments,
            document_id=document_id,
            page_id=page_id,
            page_number=page_number,
            clause_id=clause_id,
            clause_number=clause_number,
            start_index=start_index,
        )

    def _build_segments(self, text: str) -> List[str]:
        """
        Break text into the finest-grained segments: sentences.

        Paragraph boundaries are respected first (double newline → force break),
        then sentence boundaries within each paragraph.
        Sentences longer than ``chunk_size`` are hard-split by character count.
        """
        segments: List[str] = []

        # Split by paragraph first (double newline).
        paragraphs = re.split(r"\n{2,}", text)

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            sentences = _split_sentences(para)
            for sentence in sentences:
                if not sentence:
                    continue
                if _count_tokens(sentence) <= self.chunk_size:
                    segments.append(sentence)
                else:
                    # Hard-split excessively long sentences.
                    segments.extend(self._hard_split(sentence))

        return segments

    def _hard_split(self, text: str) -> List[str]:
        """
        Split *text* by character count when sentence splitting is insufficient.
        Uses a word-aligned split to avoid cutting mid-word.
        """
        words = text.split()
        chunks: List[str] = []
        current: List[str] = []
        current_tokens = 0

        for word in words:
            current.append(word)
            current_tokens += 1
            if current_tokens >= self.chunk_size:
                chunks.append(" ".join(current))
                current = []
                current_tokens = 0

        if current:
            chunks.append(" ".join(current))

        return chunks

    def _merge_segments_into_chunks(
        self,
        segments: List[str],
        document_id: uuid.UUID,
        page_id: Optional[uuid.UUID],
        page_number: int,
        clause_id: Optional[uuid.UUID],
        clause_number: Optional[str],
        start_index: int,
    ) -> List[ChunkMetadata]:
        """
        Merge sentence segments into chunks that respect ``chunk_size``
        and maintain ``chunk_overlap`` between consecutive chunks.
        """
        if not segments:
            return []

        metas: List[ChunkMetadata] = []
        local_index = 0

        # Sliding window over segments.
        seg_idx = 0
        total = len(segments)

        while seg_idx < total:
            current_tokens = 0
            window: List[str] = []

            i = seg_idx
            while i < total:
                seg_tokens = _count_tokens(segments[i])
                if window and current_tokens + seg_tokens > self.chunk_size:
                    break
                window.append(segments[i])
                current_tokens += seg_tokens
                i += 1

            if not window:
                # Single segment exceeds chunk_size (already hard-split above,
                # but guard against degenerate cases).
                window = [segments[seg_idx]]
                current_tokens = _count_tokens(window[0])
                i = seg_idx + 1

            chunk_text = " ".join(window)
            metas.append(
                ChunkMetadata(
                    document_id=document_id,
                    page_id=page_id,
                    page_number=page_number,
                    clause_id=clause_id,
                    clause_number=clause_number,
                    chunk_index=start_index + local_index,
                    text=chunk_text,
                    token_count=_count_tokens(chunk_text),
                )
            )
            local_index += 1

            # Advance by (window_size - overlap) segments.
            advance = max(1, len(window) - self._overlap_segments(window))
            seg_idx += advance

        return metas

    def _overlap_segments(self, window: List[str]) -> int:
        """
        Compute how many trailing segments from *window* should be re-included
        at the start of the next window to achieve ``chunk_overlap`` tokens.
        """
        target = self.chunk_overlap
        accumulated = 0
        count = 0
        for seg in reversed(window):
            t = _count_tokens(seg)
            if accumulated + t > target:
                break
            accumulated += t
            count += 1
        return count


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

document_chunker = DocumentChunker()
