import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, status, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.session import get_db, AsyncSessionLocal
from app.schemas.base import ApiResponse
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentStatusResponse,
    DocumentMetadataResponse,
    DocumentPageResponse,
    DocumentPagesListResponse,
    PastedTextRequest,
)
from app.models.document import Document, DocumentPage
from app.services.document_service import (
    document_service,
    DocumentValidationError,
    STATUS_PROGRESS_MAP,
)
from app.core.logging import logger

router = APIRouter(prefix="/documents", tags=["Documents"])


async def _run_async_pipeline(doc_id: uuid.UUID) -> None:
    """
    Background worker function executing the pipeline in its own DB session.
    """
    if AsyncSessionLocal is None:
        logger.error("Database session maker not initialized.")
        return

    async with AsyncSessionLocal() as db:
        try:
            await document_service.process_document_pipeline(doc_id, db)
        except Exception as e:
            logger.error("Pipeline background execution failed for %s: %s", doc_id, e)


@router.post(
    "/upload",
    response_model=ApiResponse[DocumentUploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload Legal Document",
    description="Intakes PDF, JPEG, PNG, or TIFF legal documents (max 25MB). Computes SHA-256 and begins processing."
)
async def upload_document(
    background_tasks: BackgroundTasks,
    response: Response,
    file: UploadFile = File(...),
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> ApiResponse[DocumentUploadResponse]:
    try:
        doc = await document_service.create_document_from_upload(
            file=file,
            db=db,
            session_id=session_id
        )

        # Enqueue pipeline execution in background
        background_tasks.add_task(_run_async_pipeline, doc.id)

        response_data = DocumentUploadResponse(
            document_id=doc.id,
            status=doc.status,
            filename=doc.original_filename,
            expires_at=doc.expires_at
        )
        return ApiResponse.ok(data=response_data)

    except DocumentValidationError as ve:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ApiResponse.fail(code=ve.code, message=ve.message, retryable=ve.retryable)
    except Exception as e:
        logger.error("Upload error: %s", e, exc_info=True)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiResponse.fail(
            code="UPLOAD_FAILED",
            message="An unexpected error occurred during document intake.",
            retryable=True
        )


@router.post(
    "/text",
    response_model=ApiResponse[DocumentUploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Intake Pasted Legal Text",
    description="Allows users to paste raw legal clauses or notices directly without uploading a file."
)
async def intake_pasted_text(
    payload: PastedTextRequest,
    response: Response,
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> ApiResponse[DocumentUploadResponse]:
    try:
        doc = await document_service.create_document_from_text(
            text=payload.text,
            filename=payload.filename,
            db=db,
            session_id=session_id
        )
        response_data = DocumentUploadResponse(
            document_id=doc.id,
            status=doc.status,
            filename=doc.original_filename,
            expires_at=doc.expires_at
        )
        return ApiResponse.ok(data=response_data)
    except DocumentValidationError as ve:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ApiResponse.fail(code=ve.code, message=ve.message, retryable=ve.retryable)
    except Exception as e:
        logger.error("Pasted text error: %s", e, exc_info=True)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ApiResponse.fail(
            code="INTAKE_FAILED",
            message="Failed to intake pasted text.",
            retryable=True
        )


@router.get(
    "/{document_id}/status",
    response_model=ApiResponse[DocumentStatusResponse],
    summary="Poll Document Processing Status",
    description="Returns current processing status, monotonic progress indicator (0-100), and stage."
)
async def get_document_status(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> ApiResponse[DocumentStatusResponse]:
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    doc = result.scalars().first()

    if not doc:
        return ApiResponse.fail(code="DOCUMENT_NOT_FOUND", message="Document not found.", retryable=False)

    progress, default_stage = STATUS_PROGRESS_MAP.get(doc.status, (0, "Unknown stage"))
    stage = doc.status.lower().replace("_", " ")

    status_data = DocumentStatusResponse(
        document_id=doc.id,
        status=doc.status,
        progress=progress,
        stage=default_stage,
        error=doc.error_message,
        retryable=doc.is_retryable
    )
    return ApiResponse.ok(data=status_data)


@router.get(
    "/{document_id}",
    response_model=ApiResponse[DocumentMetadataResponse],
    summary="Get Document Metadata",
    description="Returns metadata only (filename, size, MIME type, page count, expiration). Never returns binary content."
)
async def get_document_metadata(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> ApiResponse[DocumentMetadataResponse]:
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    doc = result.scalars().first()

    if not doc:
        return ApiResponse.fail(code="DOCUMENT_NOT_FOUND", message="Document not found.", retryable=False)

    metadata = DocumentMetadataResponse(
        id=doc.id,
        filename=doc.original_filename,
        mime_type=doc.mime_type,
        size=doc.file_size,
        page_count=doc.page_count,
        status=doc.status,
        created_at=doc.created_at,
        expires_at=doc.expires_at
    )
    return ApiResponse.ok(data=metadata)


@router.get(
    "/{document_id}/pages",
    response_model=ApiResponse[DocumentPagesListResponse],
    summary="Get Extracted Document Pages",
    description="Returns list of extracted pages with text, dimensions, and OCR flag for side-by-side display."
)
async def get_document_pages(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> ApiResponse[DocumentPagesListResponse]:
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    doc = result.scalars().first()

    if not doc:
        return ApiResponse.fail(code="DOCUMENT_NOT_FOUND", message="Document not found.", retryable=False)

    pages_query = select(DocumentPage).where(DocumentPage.document_id == document_id).order_by(DocumentPage.page_number)
    pages_res = await db.execute(pages_query)
    pages = list(pages_res.scalars().all())

    items = [
        DocumentPageResponse(
            page_number=p.page_number,
            text=p.extracted_text,
            ocr_used=p.ocr_used,
            ocr_confidence=p.ocr_confidence,
            width=p.width,
            height=p.height
        )
        for p in pages
    ]

    return ApiResponse.ok(
        data=DocumentPagesListResponse(
            document_id=doc.id,
            page_count=len(items),
            pages=items
        )
    )


@router.get(
    "/{document_id}/file",
    summary="Secure Document File Access",
    description="Securely streams the original legal document for side-by-side verification. Protects against path traversal."
)
async def get_original_file(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    doc = result.scalars().first()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    abs_path = document_service.storage.get_absolute_path(doc.storage_key)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on storage.")

    return FileResponse(
        path=abs_path,
        media_type=doc.mime_type,
        filename=doc.original_filename
    )


@router.delete(
    "/{document_id}",
    response_model=ApiResponse[dict],
    summary="Delete Document",
    description="Cryptographically purges document files from storage and cascades deletion in the database. Idempotent."
)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> ApiResponse[dict]:
    await document_service.delete_document(document_id, db)
    return ApiResponse.ok(data={"deleted": True, "document_id": str(document_id)})


@router.post(
    "/{document_id}/retry",
    response_model=ApiResponse[DocumentStatusResponse],
    summary="Retry Failed Document Processing",
    description="Retries processing for recoverable failures (e.g. temporary OCR or storage errors)."
)
async def retry_document_processing(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> ApiResponse[DocumentStatusResponse]:
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    doc = result.scalars().first()

    if not doc:
        return ApiResponse.fail(code="DOCUMENT_NOT_FOUND", message="Document not found.", retryable=False)

    if doc.status != "FAILED" and not doc.is_retryable:
        return ApiResponse.fail(
            code="NOT_RETRYABLE",
            message=f"Document status is '{doc.status}', not in a retryable failure state.",
            retryable=False
        )

    doc.status = "UPLOADED"
    doc.error_code = None
    doc.error_message = None
    await db.commit()

    background_tasks.add_task(_run_async_pipeline, doc.id)

    progress, default_stage = STATUS_PROGRESS_MAP.get(doc.status, (5, "Queued for retry"))
    return ApiResponse.ok(
        data=DocumentStatusResponse(
            document_id=doc.id,
            status=doc.status,
            progress=progress,
            stage=default_stage,
            error=None,
            retryable=False
        )
    )
