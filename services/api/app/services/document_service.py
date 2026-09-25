import os
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional, List
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.core.config import settings
from app.core.logging import logger
from app.models.document import Document, DocumentPage
from app.document.storage import LocalDocumentStorage, document_storage
from app.document.ocr_factory import get_ocr_provider
from app.document.extractor import DocumentExtractor
from app.classification import classification_service
from app.extraction import entity_extraction_service
from app.clauses import clause_segmentation_service
from app.rag.chunking import document_chunker
from app.rag.embeddings.factory import get_embedding_provider
from app.rag.embeddings.base import EmbeddingProviderError

# Allowed MIME types and extensions
ALLOWED_MIME_TYPES = {
    "application/pdf": [".pdf"],
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/tiff": [".tif", ".tiff"],
}

STATUS_PROGRESS_MAP = {
    "UPLOADED": (5, "Document uploaded to secure vault"),
    "VALIDATING": (10, "Validating file integrity and format"),
    "PROCESSING": (20, "Preparing extraction environment"),
    "EXTRACTING": (35, "Extracting text and page boundaries"),
    "OCR_REQUIRED": (45, "Scanned page detected, preparing OCR"),
    "OCR_PROCESSING": (55, "Performing optical character recognition"),
    "EXTRACTED": (65, "Finalizing page records"),
    "CLASSIFYING": (72, "Classifying document type"),
    "EXTRACTING_ENTITIES": (79, "Extracting action-relevant entities"),
    "SEGMENTING_CLAUSES": (86, "Segmenting document clauses"),
    "CHUNKING_DOCUMENT": (91, "Building semantic chunks"),
    "GENERATING_EMBEDDINGS": (96, "Generating vector embeddings"),
    "READY": (100, "Ready for comprehension and analysis"),
    "READY_WITHOUT_EMBEDDINGS": (98, "Ready — embedding provider unavailable"),
    "FAILED": (0, "Processing encountered an issue"),
    "DELETING": (0, "Purging document data"),
    "DELETED": (0, "Document purged permanently"),
}



class DocumentValidationError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


async def _generate_and_store_embeddings(
    document_id: uuid.UUID,
    embedding_provider,
    db: AsyncSession,
) -> int:
    """
    Batch-generate embeddings for all chunks of *document_id* and persist them.

    Uses the provider's embed_batch API so only one network round-trip is made
    per batch of EMBEDDING_BATCH_SIZE chunks.  Returns the number of chunks
    that received an embedding.

    Security note: chunk text is never logged at INFO level or above.
    """
    from sqlalchemy import select, update
    from app.models.document import DocumentChunk

    # Load all chunks for the document that don't have an embedding yet.
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = list(result.scalars().all())

    if not chunks:
        logger.info("No chunks found for document %s — skipping embedding generation.", document_id)
        return 0

    batch_size = settings.EMBEDDING_BATCH_SIZE
    total_embedded = 0

    for batch_start in range(0, len(chunks), batch_size):
        batch = chunks[batch_start : batch_start + batch_size]
        texts = [c.text for c in batch]

        vectors = await embedding_provider.embed_batch(texts)

        for chunk, vector in zip(batch, vectors):
            chunk.embedding = vector

        total_embedded += len(batch)

    await db.commit()
    logger.info(
        "Stored embeddings for %d/%d chunks (document %s).",
        total_embedded, len(chunks), document_id,
    )
    return total_embedded


class DocumentService:
    def __init__(self, storage: Optional[LocalDocumentStorage] = None):
        self.storage = storage or document_storage

    def validate_file(self, filename: str, content_type: Optional[str], file_bytes: bytes) -> str:
        """
        Strict multi-layer validation of uploaded document.
        """
        # 1. Non-empty check
        if not file_bytes or len(file_bytes) == 0:
            raise DocumentValidationError("EMPTY_FILE", "The uploaded file is empty.", retryable=False)

        # 2. Size limit check
        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise DocumentValidationError(
                "FILE_TOO_LARGE",
                f"File size exceeds maximum permitted limit of {settings.MAX_FILE_SIZE_MB}MB.",
                retryable=False
            )

        # 3. Extension check
        ext = os.path.splitext(filename)[1].lower()
        valid_ext = any(ext in exts for exts in ALLOWED_MIME_TYPES.values())
        if not valid_ext:
            raise DocumentValidationError(
                "UNSUPPORTED_FILE_TYPE",
                f"File extension '{ext}' is not supported. Allowed formats: PDF, JPEG, PNG, TIFF.",
                retryable=False
            )

        # 4. MIME type check
        detected_mime = (content_type or "").lower().split(";")[0].strip()
        if not detected_mime or detected_mime not in ALLOWED_MIME_TYPES:
            # Fallback by extension if generic binary stream
            if ext == ".pdf":
                detected_mime = "application/pdf"
            elif ext in [".jpg", ".jpeg"]:
                detected_mime = "image/jpeg"
            elif ext == ".png":
                detected_mime = "image/png"
            elif ext in [".tif", ".tiff"]:
                detected_mime = "image/tiff"
            else:
                raise DocumentValidationError(
                    "UNSUPPORTED_FILE_TYPE",
                    f"MIME type '{detected_mime}' is not supported.",
                    retryable=False
                )

        # 5. Magic byte / header sanity check
        if detected_mime == "application/pdf" and not file_bytes.startswith(b"%PDF"):
            raise DocumentValidationError(
                "CORRUPTED_FILE",
                "Invalid PDF document: missing standard PDF header.",
                retryable=False
            )

        return detected_mime

    def calculate_sha256(self, file_bytes: bytes) -> str:
        return hashlib.sha256(file_bytes).hexdigest()

    async def create_document_from_upload(
        self,
        file: UploadFile,
        db: AsyncSession,
        session_id: Optional[str] = None
    ) -> Document:
        filename = file.filename or "unknown_document"
        file_bytes = await file.read()

        mime_type = self.validate_file(filename, file.content_type, file_bytes)
        sha256_hash = self.calculate_sha256(file_bytes)

        document_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=settings.DOCUMENT_TTL_HOURS)

        # Generate safe storage key
        safe_key = self.storage.generate_storage_key(document_id, "original", filename)
        await self.storage.save_file(file_bytes, safe_key)

        doc = Document(
            id=document_id,
            session_id=session_id,
            original_filename=filename,
            storage_key=safe_key,
            mime_type=mime_type,
            file_size=len(file_bytes),
            sha256_hash=sha256_hash,
            status="UPLOADED",
            page_count=0,
            ocr_required=False,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            is_retryable=False,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        return doc

    async def create_document_from_text(
        self,
        text: str,
        filename: Optional[str],
        db: AsyncSession,
        session_id: Optional[str] = None
    ) -> Document:
        cleaned_text = text.strip()
        if not cleaned_text:
            raise DocumentValidationError("EMPTY_FILE", "Pasted text content cannot be empty.", retryable=False)

        file_bytes = cleaned_text.encode("utf-8")
        actual_filename = filename or "pasted-legal-document.txt"
        sha256_hash = self.calculate_sha256(file_bytes)

        document_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=settings.DOCUMENT_TTL_HOURS)

        safe_key = self.storage.generate_storage_key(document_id, "original", actual_filename)
        await self.storage.save_file(file_bytes, safe_key)

        doc = Document(
            id=document_id,
            session_id=session_id,
            original_filename=actual_filename,
            storage_key=safe_key,
            mime_type="text/plain",
            file_size=len(file_bytes),
            sha256_hash=sha256_hash,
            status="READY",
            page_count=1,
            ocr_required=False,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            is_retryable=False,
        )
        db.add(doc)
        await db.flush()

        page = DocumentPage(
            id=uuid.uuid4(),
            document_id=document_id,
            page_number=1,
            extracted_text=cleaned_text,
            ocr_used=False,
            created_at=now,
            updated_at=now
        )
        db.add(page)
        await db.commit()

        # Run intelligence pipeline on pasted text document
        await classification_service.classify_and_persist(document_id, db)
        await entity_extraction_service.extract_and_persist(document_id, db)
        await clause_segmentation_service.segment_and_persist(document_id, db)
        await document_chunker.chunk_and_persist(document_id, db)

        try:
            embedding_provider = get_embedding_provider()
            await _generate_and_store_embeddings(document_id, embedding_provider, db)
        except EmbeddingProviderError:
            pass  # Embeddings are optional for pasted text; doc remains READY

        await db.refresh(doc)
        return doc

    async def process_document_pipeline(self, document_id: uuid.UUID, db: AsyncSession) -> Document:
        """
        Executes the extraction and OCR pipeline followed by Phase 3 document intelligence.
        Designed to be called synchronously by API or asynchronously by Celery worker.
        """
        query = select(Document).where(Document.id == document_id)
        result = await db.execute(query)
        doc = result.scalars().first()

        if not doc:
            raise ValueError(f"Document {document_id} not found.")

        try:
            # 1. VALIDATING
            doc.status = "VALIDATING"
            doc.updated_at = datetime.now(timezone.utc)
            await db.commit()

            # 2. PROCESSING
            doc.status = "PROCESSING"
            doc.updated_at = datetime.now(timezone.utc)
            await db.commit()

            # 3. EXTRACTING
            doc.status = "EXTRACTING"
            doc.updated_at = datetime.now(timezone.utc)
            await db.commit()

            abs_file_path = self.storage.get_absolute_path(doc.storage_key)
            if not os.path.exists(abs_file_path):
                raise FileNotFoundError(f"Underlying document file not found at {abs_file_path}")

            ocr_provider = get_ocr_provider()
            extractor = DocumentExtractor(storage=self.storage, ocr_provider=ocr_provider)

            if doc.mime_type.startswith("image/"):
                doc.status = "OCR_PROCESSING"
                await db.commit()

            extracted = await extractor.extract(doc.id, abs_file_path, doc.mime_type)

            if extracted.ocr_required:
                doc.status = "OCR_PROCESSING"
                doc.ocr_required = True
                await db.commit()

            # 4. Clear any previous pages on retry
            await db.execute(delete(DocumentPage).where(DocumentPage.document_id == doc.id))

            # 5. Insert extracted page records
            now = datetime.now(timezone.utc)
            for p in extracted.pages:
                page_record = DocumentPage(
                    id=uuid.uuid4(),
                    document_id=doc.id,
                    page_number=p.page_number,
                    storage_key=p.image_storage_key,
                    extracted_text=p.text,
                    ocr_used=p.ocr_used,
                    ocr_confidence=p.ocr_confidence,
                    width=p.width,
                    height=p.height,
                    created_at=now,
                    updated_at=now
                )
                db.add(page_record)

            doc.page_count = extracted.total_pages
            doc.status = "EXTRACTED"
            doc.updated_at = datetime.now(timezone.utc)
            await db.commit()

            # 6. CLASSIFYING (Phase 3)
            doc.status = "CLASSIFYING"
            doc.updated_at = datetime.now(timezone.utc)
            await db.commit()
            await classification_service.classify_and_persist(doc.id, db)

            # 7. EXTRACTING_ENTITIES (Phase 3)
            doc.status = "EXTRACTING_ENTITIES"
            doc.updated_at = datetime.now(timezone.utc)
            await db.commit()
            await entity_extraction_service.extract_and_persist(doc.id, db)

            # 8. SEGMENTING_CLAUSES (Phase 3)
            doc.status = "SEGMENTING_CLAUSES"
            doc.updated_at = datetime.now(timezone.utc)
            await db.commit()
            await clause_segmentation_service.segment_and_persist(doc.id, db)

            # 9. CHUNKING_DOCUMENT (Phase 4)
            doc.status = "CHUNKING_DOCUMENT"
            doc.updated_at = datetime.now(timezone.utc)
            await db.commit()
            await document_chunker.chunk_and_persist(doc.id, db)

            # 10. GENERATING_EMBEDDINGS (Phase 4)
            doc.status = "GENERATING_EMBEDDINGS"
            doc.updated_at = datetime.now(timezone.utc)
            await db.commit()

            try:
                embedding_provider = get_embedding_provider()
                await _generate_and_store_embeddings(doc.id, embedding_provider, db)
                final_status = "READY"
            except EmbeddingProviderError as emb_err:
                # Embedding provider not configured — document is still useful
                # for classification, entity extraction, and clause browsing.
                logger.warning(
                    "Embedding provider unavailable for document %s: %s. "
                    "Document will be READY_WITHOUT_EMBEDDINGS.",
                    doc.id, emb_err,
                )
                final_status = "READY_WITHOUT_EMBEDDINGS"

            # 11. READY (or READY_WITHOUT_EMBEDDINGS)
            doc.status = final_status
            doc.updated_at = datetime.now(timezone.utc)
            doc.error_code = None
            doc.error_message = None
            doc.is_retryable = False

            await db.commit()
            await db.refresh(doc)
            return doc


        except Exception as e:
            logger.error("Error processing document %s: %s", document_id, e, exc_info=True)
            doc.status = "FAILED"
            doc.error_code = "PROCESSING_ERROR"
            doc.error_message = str(e)
            doc.is_retryable = True
            doc.updated_at = datetime.now(timezone.utc)
            await db.commit()
            return doc

    async def delete_document(self, document_id: uuid.UUID, db: AsyncSession) -> bool:
        """
        Idempotently deletes document files from disk and cascades database deletion.
        """
        query = select(Document).where(Document.id == document_id)
        result = await db.execute(query)
        doc = result.scalars().first()

        # Delete physical storage directory
        self.storage.delete_document_tree(document_id)

        if doc:
            await db.delete(doc)
            await db.commit()

        return True

    async def retry_document(self, document_id: uuid.UUID, db: AsyncSession) -> Document:
        query = select(Document).where(Document.id == document_id)
        result = await db.execute(query)
        doc = result.scalars().first()

        if not doc:
            raise DocumentValidationError("NOT_FOUND", "Document not found.", retryable=False)

        if doc.status != "FAILED" and not doc.is_retryable:
            raise DocumentValidationError("NOT_RETRYABLE", "Document is not in a retryable state.", retryable=False)

        doc.status = "UPLOADED"
        doc.error_code = None
        doc.error_message = None
        doc.updated_at = datetime.now(timezone.utc)
        await db.commit()

        # Execute processing pipeline
        return await self.process_document_pipeline(document_id, db)

    async def cleanup_expired_documents(self, db: AsyncSession) -> int:
        """
        Purges expired documents whose TTL has elapsed.
        """
        now = datetime.now(timezone.utc)
        query = select(Document).where(Document.expires_at <= now)
        result = await db.execute(query)
        expired_docs = list(result.scalars().all())

        purged_count = 0
        for doc in expired_docs:
            self.storage.delete_document_tree(doc.id)
            await db.delete(doc)
            purged_count += 1

        if purged_count > 0:
            await db.commit()
            logger.info("Purged %d expired documents (TTL compliance).", purged_count)

        return purged_count


document_service = DocumentService()
