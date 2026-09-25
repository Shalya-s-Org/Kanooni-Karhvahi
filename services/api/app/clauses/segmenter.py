import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.document import Document, DocumentPage, DocumentClause


class ExtractedClause:
    def __init__(
        self,
        clause_number: Optional[str],
        title: Optional[str],
        original_text: str,
        page_start: int,
        page_end: int,
        confidence: float,
        page_id: Optional[uuid.UUID] = None,
    ):
        self.clause_number = clause_number
        self.title = title
        self.original_text = original_text
        self.page_start = page_start
        self.page_end = page_end
        self.confidence = confidence
        self.page_id = page_id


class ClauseSegmentationService:
    """
    Deterministic clause and section segmentation service.
    Detects numbered clauses, article headers, standard legal clause titles,
    and conservative paragraph blocks.
    Strictly preserves verbatim original text without AI summaries or interpretation.
    """

    # 1. Numbered / Heading patterns:
    # "1. Definitions", "1.1 Scope", "Clause 4. Payment Terms", "ARTICLE II: REPRESENTATIONS", "SECTION 3 -"
    P_CLAUSE_HEADER = re.compile(
        r"^(?:(?P<prefix>(?:clause|section|article)\s+)?(?P<num>\d+(?:\.\d+)*|[IVXLCDM]+)[\.\:\-–]?\s*(?P<title>[A-Z][A-Za-z0-9\s,\/&\(\)]+)?|WHEREAS|NOW\s+THEREFORE|DEFINITIONS|TERMS\s+AND\s+CONDITIONS|GOVERNING\s+LAW|JURISDICTION|TERMINATION|CONFIDENTIALITY|INDEMNIFICATION|DISPUTE\s+RESOLUTION|FORCE\s+MAJEURE)$",
        re.IGNORECASE
    )

    # Inline clause start: "1. Definitions: ...", "Clause 2. Term: ..."
    P_INLINE_HEADER = re.compile(
        r"^(?P<num>(?:clause|section|article\s+)?[0-9]+(?:\.[0-9]+)*|[IVXLCDM]+)[\.\:\-–]\s+(?:(?P<title>[A-Z][A-Za-z0-9\s\/&\(\)]{2,40})[\:\-–\.\n])?\s*(?P<bodyText>.*)$",
        re.IGNORECASE
    )

    STANDARD_TITLES = [
        "DEFINITIONS",
        "SCOPE OF WORK",
        "OBLIGATIONS",
        "CONSIDERATION",
        "PAYMENT TERMS",
        "TERM AND TERMINATION",
        "CONFIDENTIALITY",
        "INTELLECTUAL PROPERTY",
        "INDEMNIFICATION",
        "LIMITATION OF LIABILITY",
        "REPRESENTATIONS AND WARRANTIES",
        "GOVERNING LAW",
        "JURISDICTION",
        "DISPUTE RESOLUTION",
        "ARBITRATION",
        "FORCE MAJEURE",
        "MISCELLANEOUS",
        "SEVERABILITY",
        "SCHEDULE OF PROPERTY",
        "TERMS AND CONDITIONS",
    ]

    def segment_text(self, pages: List[Tuple[int, str, Optional[uuid.UUID]]]) -> List[ExtractedClause]:
        """
        Segments text across pages into logical clauses.
        :param pages: List of (page_number, text, page_id)
        """
        clauses: List[ExtractedClause] = []

        current_num: Optional[str] = None
        current_title: Optional[str] = None
        current_lines: List[str] = []
        current_page_start: int = 1
        current_page_end: int = 1
        current_page_id: Optional[uuid.UUID] = None
        current_conf: float = 0.85

        def flush():
            nonlocal current_num, current_title, current_lines, current_page_start, current_page_end, current_page_id, current_conf
            body = "\n".join(current_lines).strip()
            if body and len(body) >= 15:  # meaningful content filter
                clauses.append(
                    ExtractedClause(
                        clause_number=current_num,
                        title=current_title,
                        original_text=body,
                        page_start=current_page_start,
                        page_end=current_page_end,
                        confidence=current_conf,
                        page_id=current_page_id,
                    )
                )
            current_num = None
            current_title = None
            current_lines = []
            current_conf = 0.85

        for page_num, text, page_id in pages:
            lines = text.splitlines()
            for line in lines:
                raw_line = line.strip()
                if not raw_line:
                    continue

                # Check if this line is a standalone header / clause start
                m_header = self.P_CLAUSE_HEADER.match(raw_line)
                if m_header:
                    flush()
                    num = m_header.group("num") if "num" in m_header.groupdict() else None
                    title = m_header.group("title") if "title" in m_header.groupdict() else None

                    # If no regex groups matched but line is standard title
                    if not num and not title:
                        upper_line = raw_line.upper()
                        if any(st in upper_line for st in self.STANDARD_TITLES) or raw_line.isupper():
                            title = raw_line

                    current_num = num
                    current_title = title.strip() if title else None
                    current_page_start = page_num
                    current_page_end = page_num
                    current_page_id = page_id
                    current_conf = 0.95
                    current_lines.append(raw_line)
                    continue

                # Check inline header: "1. Term: The term of this agreement..."
                m_inline = self.P_INLINE_HEADER.match(raw_line)
                if m_inline:
                    flush()
                    num = m_inline.group("num")
                    title = m_inline.group("title")
                    current_num = num.strip() if num else None
                    current_title = title.strip() if title else None
                    current_page_start = page_num
                    current_page_end = page_num
                    current_page_id = page_id
                    current_conf = 0.92
                    current_lines.append(raw_line)
                    continue

                # Check if line matches a standard title in all caps
                if raw_line.upper() in self.STANDARD_TITLES or (len(raw_line) < 50 and raw_line.isupper() and len(raw_line.split()) <= 5):
                    flush()
                    current_title = raw_line
                    current_page_start = page_num
                    current_page_end = page_num
                    current_page_id = page_id
                    current_conf = 0.90
                    current_lines.append(raw_line)
                    continue

                # Normal continuation line
                if not current_lines:
                    current_page_start = page_num
                    current_page_id = page_id
                current_page_end = page_num
                current_lines.append(raw_line)

        # Final flush
        flush()

        # Fallback: if no clauses were detected (e.g. unformatted single block),
        # segment into paragraphs
        if not clauses:
            for page_num, text, page_id in pages:
                paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
                for idx, p in enumerate(paragraphs):
                    if len(p) >= 15:
                        clauses.append(
                            ExtractedClause(
                                clause_number=f"Para {idx + 1}",
                                title=None,
                                original_text=p,
                                page_start=page_num,
                                page_end=page_num,
                                confidence=0.75,
                                page_id=page_id,
                            )
                        )

        return clauses

    async def segment_and_persist(
        self,
        document_id: uuid.UUID,
        db: AsyncSession
    ) -> List[DocumentClause]:
        """
        Segments clauses across all document pages and persists to DocumentClause.
        """
        doc_query = select(Document).where(Document.id == document_id)
        doc_res = await db.execute(doc_query)
        doc = doc_res.scalars().first()
        if not doc:
            raise ValueError(f"Document {document_id} not found.")

        pages_query = (
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
        )
        pages_res = await db.execute(pages_query)
        pages = list(pages_res.scalars().all())

        page_data = [(p.page_number, p.extracted_text, p.id) for p in pages]
        extracted_clauses = self.segment_text(page_data)

        # Clear existing clauses for this document
        await db.execute(
            delete(DocumentClause).where(DocumentClause.document_id == document_id)
        )

        now = datetime.now(timezone.utc)
        saved_clauses: List[DocumentClause] = []

        for ec in extracted_clauses:
            clause_record = DocumentClause(
                id=uuid.uuid4(),
                document_id=doc.id,
                page_id=ec.page_id,
                clause_number=ec.clause_number,
                title=ec.title,
                original_text=ec.original_text,
                page_start=ec.page_start,
                page_end=ec.page_end,
                confidence=ec.confidence,
                created_at=now
            )
            db.add(clause_record)
            saved_clauses.append(clause_record)

        await db.commit()
        return saved_clauses


clause_segmentation_service = ClauseSegmentationService()
