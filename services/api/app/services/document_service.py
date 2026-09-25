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

# Allowed MIME types and extensions
ALLOWED_MIME_TYPES = {
    "application/pdf": [".pdf"],
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/tiff": [".tif", ".tiff"],
}

STATUS_PROGRESS_MAP = {
    "UPLOADED": (5, "Document uploaded to secure vault"),
    "VALIDATING": (15, "Validating file integrity and format"),
    "PROCESSING": (25, "Preparing extraction environment"),
    "EXTRACTING": (45, "Extracting text and page boundaries"),
    "OCR_REQUIRED": (55, "Scanned page detected, preparing OCR"),
    "OCR_PROCESSING": (75, "Performing optical character recognition"),
    "EXTRACTED": (90, "Finalizing page records"),
    "READY": (100, "Ready for comprehension and analysis"),
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
        await db.refresh(doc)
        return doc

    async def process_document_pipeline(self, document_id: uuid.UUID, db: AsyncSession) -> Document:
        """
        Executes the extraction and OCR pipeline.
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

            # 6. READY
            doc.status = "READY"
            doc.page_count = extracted.total_pages
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
