import uuid
from datetime import datetime, timezone
from typing import List, Sequence, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.document import Document, DocumentPage, DocumentEntity
from app.extraction.base import BaseEntityExtractor
from app.extraction.models import RawExtractedEntity
from app.extraction.date_extractor import DateExtractor
from app.extraction.amount_extractor import AmountExtractor
from app.extraction.parties_extractor import PartiesExtractor
from app.extraction.authorities_extractor import AuthoritiesExtractor
from app.extraction.reference_extractor import ReferenceExtractor
from app.extraction.legal_sections_extractor import LegalSectionsExtractor
from app.extraction.contact_extractor import ContactExtractor


class EntityExtractionService:
    """
    Coordinates modular deterministic entity extractors, aggregates extracted
    entities across document pages, preserves traceability, and handles persistence.
    """

    def __init__(self, extractors: Optional[List[BaseEntityExtractor]] = None):
        self.extractors = extractors or [
            DateExtractor(),
            AmountExtractor(),
            PartiesExtractor(),
            AuthoritiesExtractor(),
            ReferenceExtractor(),
            LegalSectionsExtractor(),
            ContactExtractor(),
        ]

    def extract_from_page(self, text: str, page_number: int) -> List[RawExtractedEntity]:
        """
        Runs all registered extractors on a single page's text.
        """
        results: List[RawExtractedEntity] = []
        for extractor in self.extractors:
            try:
                extracted = extractor.extract(text=text, page_number=page_number)
                results.extend(extracted)
            except Exception as e:
                # Keep individual extractor failures isolated
                continue
        return results

    async def extract_and_persist(
        self,
        document_id: uuid.UUID,
        db: AsyncSession
    ) -> List[DocumentEntity]:
        """
        Extracts entities for all pages of the document, clears previous entities (for retries),
        and commits new DocumentEntity records.
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

        # Clear existing entities for this document
        await db.execute(
            delete(DocumentEntity).where(DocumentEntity.document_id == document_id)
        )

        now = datetime.now(timezone.utc)
        saved_entities: List[DocumentEntity] = []

        for p in pages:
            raw_entities = self.extract_from_page(p.extracted_text, p.page_number)
            for raw in raw_entities:
                entity_record = DocumentEntity(
                    id=uuid.uuid4(),
                    document_id=doc.id,
                    page_id=p.id,
                    page_number=p.page_number,
                    entity_type=raw.entity_type,
                    value=raw.value,
                    normalized_value=raw.normalized_value,
                    entity_metadata=raw.metadata,
                    source_text=raw.source_text,
                    start_offset=raw.start_offset,
                    end_offset=raw.end_offset,
                    confidence=raw.confidence,
                    created_at=now
                )
                db.add(entity_record)
                saved_entities.append(entity_record)

        await db.commit()
        return saved_entities


entity_extraction_service = EntityExtractionService()
