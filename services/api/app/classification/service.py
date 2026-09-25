import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.document import Document, DocumentPage, DocumentClassification
from app.classification.base import BaseDocumentClassifier, DocumentClassificationResult
from app.classification.rule_based_classifier import RuleBasedDocumentClassifier


class DocumentClassificationService:
    """
    Coordinates document classification, delegates to configured classification strategy,
    and manages classification persistence.
    """

    def __init__(self, classifier: Optional[BaseDocumentClassifier] = None):
        self.classifier = classifier or RuleBasedDocumentClassifier()

    async def classify_pages(
        self,
        pages: Sequence[Tuple[int, str]],
        filename: str = ""
    ) -> DocumentClassificationResult:
        """
        Classifies page tuples directly without requiring DB access.
        """
        return await self.classifier.classify(pages=pages, filename=filename)

    async def classify_and_persist(
        self,
        document_id: uuid.UUID,
        db: AsyncSession
    ) -> DocumentClassificationResult:
        """
        Loads document pages, executes classification, saves/updates record in database.
        """
        # Fetch document and its pages
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

        page_tuples = [(p.page_number, p.extracted_text) for p in pages]
        result = await self.classifier.classify(page_tuples, filename=doc.original_filename)

        # Clear any existing classification for this document
        await db.execute(
            delete(DocumentClassification).where(DocumentClassification.document_id == document_id)
        )

        now = datetime.now(timezone.utc)
        record = DocumentClassification(
            id=uuid.uuid4(),
            document_id=document_id,
            document_type=result.document_type,
            confidence=result.confidence,
            evidence=[e.model_dump() for e in result.evidence],
            created_at=now
        )
        db.add(record)
        await db.commit()
        return result


classification_service = DocumentClassificationService()
