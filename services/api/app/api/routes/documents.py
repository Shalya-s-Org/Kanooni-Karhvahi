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
from app.schemas.intelligence import (
    ClassificationResponse,
    ClassificationEvidenceSchema,
    EntityResponse,
    EntityListResponse,
    ClauseResponse,
    ClauseListResponse,
)
from app.models.document import (
    Document,
    DocumentPage,
    DocumentClassification,
    DocumentEntity,
    DocumentClause,
)
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


@router.get(
    "/{document_id}/classification",
    response_model=ApiResponse[ClassificationResponse],
    summary="Get Document Classification",
    description="Returns broad legal document type, calibrated confidence, and traceable evidence snippets."
)
async def get_document_classification(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> ApiResponse[ClassificationResponse]:
    doc_query = select(Document).where(Document.id == document_id)
    doc_res = await db.execute(doc_query)
    doc = doc_res.scalars().first()
    if not doc:
        return ApiResponse.fail(code="DOCUMENT_NOT_FOUND", message="Document not found.", retryable=False)

    cls_query = select(DocumentClassification).where(DocumentClassification.document_id == document_id)
    cls_res = await db.execute(cls_query)
    classification = cls_res.scalars().first()

    if not classification:
        return ApiResponse.fail(
            code="CLASSIFICATION_NOT_FOUND",
            message="Classification not yet available. Document may still be processing.",
            retryable=True
        )

    evidence_items = [
        ClassificationEvidenceSchema(page=e.get("page", 1), text=e.get("text", ""))
        for e in (classification.evidence or [])
    ]

    return ApiResponse.ok(
        data=ClassificationResponse(
            document_type=classification.document_type,
            confidence=classification.confidence,
            evidence=evidence_items
        )
    )


@router.get(
    "/{document_id}/entities",
    response_model=ApiResponse[EntityListResponse],
    summary="Get Extracted Legal Entities",
    description="Returns structured entities (dates, deadlines, amounts, parties, authorities, reference numbers, legal sections) with optional ?type= filter."
)
async def get_document_entities(
    document_id: uuid.UUID,
    type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> ApiResponse[EntityListResponse]:
    doc_query = select(Document).where(Document.id == document_id)
    doc_res = await db.execute(doc_query)
    doc = doc_res.scalars().first()
    if not doc:
        return ApiResponse.fail(code="DOCUMENT_NOT_FOUND", message="Document not found.", retryable=False)

    query = select(DocumentEntity).where(DocumentEntity.document_id == document_id)

    if type:
        norm_type = type.upper().strip()
        # Convenience mapping: ?type=PARTY can match PERSON or ORGANIZATION
        if norm_type == "PARTY":
            query = query.where(DocumentEntity.entity_type.in_(["PERSON", "ORGANIZATION"]))
        elif norm_type in ["DATE", "DEADLINE"]:
            # If user asks for DATE, return DATE and DEADLINE
            if norm_type == "DATE":
                query = query.where(DocumentEntity.entity_type.in_(["DATE", "DEADLINE"]))
            else:
                query = query.where(DocumentEntity.entity_type == "DEADLINE")
        else:
            query = query.where(DocumentEntity.entity_type == norm_type)

    query = query.order_by(DocumentEntity.page_number, DocumentEntity.start_offset)
    result = await db.execute(query)
    entities = list(result.scalars().all())

    items = [
        EntityResponse(
            id=e.id,
            document_id=e.document_id,
            page_id=e.page_id,
            page_number=e.page_number,
            entity_type=e.entity_type,
            value=e.value,
            normalized_value=e.normalized_value,
            entity_metadata=e.entity_metadata,
            source_text=e.source_text,
            start_offset=e.start_offset,
            end_offset=e.end_offset,
            confidence=e.confidence,
            created_at=e.created_at
        )
        for e in entities
    ]

    return ApiResponse.ok(
        data=EntityListResponse(
            document_id=doc.id,
            total_count=len(items),
            entities=items
        )
    )


@router.get(
    "/{document_id}/clauses",
    response_model=ApiResponse[ClauseListResponse],
    summary="Get Document Clauses",
    description="Returns identified logical clauses and sections with page boundaries and verbatim text."
)
async def get_document_clauses(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> ApiResponse[ClauseListResponse]:
    doc_query = select(Document).where(Document.id == document_id)
    doc_res = await db.execute(doc_query)
    doc = doc_res.scalars().first()
    if not doc:
        return ApiResponse.fail(code="DOCUMENT_NOT_FOUND", message="Document not found.", retryable=False)

    query = (
        select(DocumentClause)
        .where(DocumentClause.document_id == document_id)
        .order_by(DocumentClause.page_start, DocumentClause.id)
    )
    result = await db.execute(query)
    clauses = list(result.scalars().all())

    items = [
        ClauseResponse(
            id=c.id,
            document_id=c.document_id,
            page_id=c.page_id,
            clause_number=c.clause_number,
            title=c.title,
            original_text=c.original_text,
            page_start=c.page_start,
            page_end=c.page_end,
            confidence=c.confidence,
            created_at=c.created_at
        )
        for c in clauses
    ]

    return ApiResponse.ok(
        data=ClauseListResponse(
            document_id=doc.id,
            total_count=len(items),
            clauses=items
        )
    )


@router.get(
    "/{document_id}/clauses/{clause_id}",
    response_model=ApiResponse[ClauseResponse],
    summary="Get Specific Clause",
    description="Returns details and source context for a specific clause."
)
async def get_specific_clause(
    document_id: uuid.UUID,
    clause_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> ApiResponse[ClauseResponse]:
    query = (
        select(DocumentClause)
        .where(
            DocumentClause.document_id == document_id,
            DocumentClause.id == clause_id
        )
    )
    result = await db.execute(query)
    clause = result.scalars().first()

    if not clause:
        return ApiResponse.fail(code="CLAUSE_NOT_FOUND", message="Clause not found.", retryable=False)

    return ApiResponse.ok(
        data=ClauseResponse(
            id=clause.id,
            document_id=clause.document_id,
            page_id=clause.page_id,
            clause_number=clause.clause_number,
            title=clause.title,
            original_text=clause.original_text,
            page_start=clause.page_start,
            page_end=clause.page_end,
            confidence=clause.confidence,
            created_at=clause.created_at
        )
    )



# ---------------------------------------------------------------------------
# Phase 4: Semantic Retrieval endpoint
# ---------------------------------------------------------------------------
from app.schemas.retrieval import RetrieveRequest, RetrievalResponseData, RetrievalResultSchema
from app.rag.retrieval.service import document_retrieval_service
from app.rag.embeddings.base import EmbeddingProviderError


@router.post(
    "/{document_id}/retrieve",
    response_model=ApiResponse[RetrievalResponseData],
    summary="Semantic Document Retrieval (Phase 4)",
    description=(
        "Retrieves the most semantically similar chunks from the specified document "
        "for a given query using pgvector cosine similarity. "
        "This endpoint returns evidence only — it does NOT generate an answer. "
        "Every result includes full source traceability (page, clause, chunk). "
        "Document isolation is enforced at SQL level: queries never cross document boundaries."
    ),
)
async def retrieve_document_chunks(
    document_id: uuid.UUID,
    payload: RetrieveRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[RetrievalResponseData]:
    """
    POST /api/v1/documents/{document_id}/retrieve

    Request::

        {
          "query": "What is the payment deadline?",
          "top_k": 5
        }

    Response data::

        {
          "document_id": "...",
          "query": "What is the payment deadline?",
          "results": [
            {
              "chunk_id": "...",
              "text": "...",
              "score": 0.91,
              "page_number": 4,
              "clause_id": "...",
              "clause_number": "3",
              ...
            }
          ],
          "total_results": 1,
          "retrieval_method": "semantic"
        }
    """
    try:
        results = await document_retrieval_service.retrieve(
            document_id=document_id,
            query=payload.query,
            top_k=payload.top_k,
            db=db,
        )

        retrieval_method = results[0].retrieval_method if results else "semantic"

        result_schemas = [
            RetrievalResultSchema(
                chunk_id=r.chunk_id,
                text=r.text,
                score=round(r.score, 6),
                page_number=r.page_number,
                page_id=r.page_id,
                clause_id=r.clause_id,
                clause_number=r.clause_number,
                document_id=r.document_id,
                retrieval_method=r.retrieval_method,
                source_type=r.source_type,
            )
            for r in results
        ]

        return ApiResponse.ok(
            data=RetrievalResponseData(
                document_id=document_id,
                query=payload.query,
                results=result_schemas,
                total_results=len(result_schemas),
                retrieval_method=retrieval_method,
            )
        )

    except EmbeddingProviderError as emb_err:
        logger.warning("Retrieval failed — embedding provider unavailable: %s", emb_err)
        return ApiResponse.fail(
            code="EMBEDDING_PROVIDER_UNAVAILABLE",
            message=(
                "Semantic retrieval is unavailable because the embedding provider "
                "is not configured.  Set EMBEDDING_PROVIDER=mock for development "
                "or configure a real provider."
            ),
            retryable=False,
        )

    except ValueError as ve:
        return ApiResponse.fail(
            code="RETRIEVAL_ERROR",
            message=str(ve),
            retryable=False,
        )

    except Exception as e:
        logger.error("Retrieval endpoint error for document %s: %s", document_id, e, exc_info=True)
        return ApiResponse.fail(
            code="RETRIEVAL_FAILED",
            message="An unexpected error occurred during retrieval.",
            retryable=True,
        )
