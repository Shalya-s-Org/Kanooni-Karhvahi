import os
import io
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient
from PIL import Image
import fitz  # PyMuPDF
from app.services.document_service import document_service
from app.models.document import Document, DocumentPage


def create_sample_pdf(num_pages: int = 2, text: str = "This is a legal notice regarding Section 138 of Negotiable Instruments Act.") -> bytes:
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 72), f"Page {i + 1}: {text}", fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_sample_png(width: int = 200, height: int = 100) -> bytes:
    img = Image.new("RGB", (width, height), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_valid_pdf_upload_and_pipeline(async_client: AsyncClient, test_db_session):
    """
    Test 1: Valid PDF upload -> database record -> SHA256 -> pipeline processing -> READY state.
    """
    pdf_bytes = create_sample_pdf(num_pages=2, text="Arbitration agreement between Party A and Party B.")
    files = {"file": ("contract.pdf", pdf_bytes, "application/pdf")}

    response = await async_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 201
    payload = response.json()
    assert payload["success"] is True

    doc_id = uuid.UUID(payload["data"]["document_id"])
    assert payload["data"]["status"] == "UPLOADED"
    assert payload["data"]["filename"] == "contract.pdf"

    # Execute processing pipeline directly
    doc = await document_service.process_document_pipeline(doc_id, test_db_session)
    assert doc.status == "READY"
    assert doc.page_count == 2
    assert doc.ocr_required is False
    assert len(doc.sha256_hash) == 64

    # Verify status endpoint
    status_res = await async_client.get(f"/api/v1/documents/{doc_id}/status")
    assert status_res.status_code == 200
    s_data = status_res.json()["data"]
    assert s_data["status"] == "READY"
    assert s_data["progress"] == 100

    # Verify pages endpoint
    pages_res = await async_client.get(f"/api/v1/documents/{doc_id}/pages")
    assert pages_res.status_code == 200
    p_data = pages_res.json()["data"]
    assert p_data["page_count"] == 2
    assert len(p_data["pages"]) == 2
    assert p_data["pages"][0]["page_number"] == 1
    assert "Arbitration agreement" in p_data["pages"][0]["text"]
    assert p_data["pages"][0]["ocr_used"] is False

    # Verify metadata endpoint
    meta_res = await async_client.get(f"/api/v1/documents/{doc_id}")
    assert meta_res.status_code == 200
    m_data = meta_res.json()["data"]
    assert m_data["filename"] == "contract.pdf"
    assert m_data["page_count"] == 2


@pytest.mark.asyncio
async def test_valid_image_upload_and_ocr(async_client: AsyncClient, test_db_session):
    """
    Test 2: Valid PNG image upload -> OCR trigger -> page 1 creation.
    """
    png_bytes = create_sample_png()
    files = {"file": ("affidavit.png", png_bytes, "image/png")}

    response = await async_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 201
    doc_id = uuid.UUID(response.json()["data"]["document_id"])

    # Process pipeline
    doc = await document_service.process_document_pipeline(doc_id, test_db_session)
    assert doc.status == "READY"
    assert doc.page_count == 1
    assert doc.ocr_required is True

    # Check pages endpoint
    pages_res = await async_client.get(f"/api/v1/documents/{doc_id}/pages")
    p_data = pages_res.json()["data"]
    assert p_data["page_count"] == 1
    assert p_data["pages"][0]["ocr_used"] is True
    assert p_data["pages"][0]["width"] == 200
    assert p_data["pages"][0]["height"] == 100


@pytest.mark.asyncio
async def test_unsupported_file_type_rejected(async_client: AsyncClient):
    """
    Test 3: Unsupported file type (.exe) is rejected with UNSUPPORTED_FILE_TYPE.
    """
    files = {"file": ("malware.exe", b"MZ\x90\x00", "application/x-msdownload")}
    response = await async_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "UNSUPPORTED_FILE_TYPE"
    assert payload["error"]["retryable"] is False


@pytest.mark.asyncio
async def test_empty_file_rejected(async_client: AsyncClient):
    """
    Test 4: Empty file upload is rejected with EMPTY_FILE.
    """
    files = {"file": ("empty.pdf", b"", "application/pdf")}
    response = await async_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "EMPTY_FILE"


@pytest.mark.asyncio
async def test_corrupted_pdf_rejected(async_client: AsyncClient):
    """
    Test 5: Corrupted PDF file missing %PDF header is rejected.
    """
    files = {"file": ("corrupted.pdf", b"NOT A VALID PDF FILE", "application/pdf")}
    response = await async_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "CORRUPTED_FILE"


@pytest.mark.asyncio
async def test_pasted_text_intake(async_client: AsyncClient, test_db_session):
    """
    Test 6: Intake pasted text via /text endpoint.
    """
    payload = {
        "text": "Whereas Party 1 agrees to lease the residential premises at Mumbai...",
        "filename": "lease-clause.txt"
    }
    response = await async_client.post("/api/v1/documents/text", json=payload)
    assert response.status_code == 201
    data = response.json()["data"]
    doc_id = data["document_id"]
    assert data["status"] == "READY"

    # Verify pages
    pages_res = await async_client.get(f"/api/v1/documents/{doc_id}/pages")
    p_data = pages_res.json()["data"]
    assert p_data["page_count"] == 1
    assert "residential premises at Mumbai" in p_data["pages"][0]["text"]
    assert p_data["pages"][0]["ocr_used"] is False


@pytest.mark.asyncio
async def test_original_document_secure_file_access(async_client: AsyncClient):
    """
    Test 7: Secure download/streaming of original uploaded file.
    """
    pdf_bytes = create_sample_pdf(num_pages=1, text="Original document content verification.")
    files = {"file": ("original.pdf", pdf_bytes, "application/pdf")}
    up_res = await async_client.post("/api/v1/documents/upload", files=files)
    doc_id = up_res.json()["data"]["document_id"]

    # Fetch file
    file_res = await async_client.get(f"/api/v1/documents/{doc_id}/file")
    assert file_res.status_code == 200
    assert file_res.content == pdf_bytes


@pytest.mark.asyncio
async def test_document_deletion(async_client: AsyncClient, test_db_session):
    """
    Test 8: Cryptographic and database cascaded deletion.
    """
    pdf_bytes = create_sample_pdf(num_pages=1, text="Temporary confidential document.")
    files = {"file": ("delete_me.pdf", pdf_bytes, "application/pdf")}
    up_res = await async_client.post("/api/v1/documents/upload", files=files)
    doc_id = uuid.UUID(up_res.json()["data"]["document_id"])

    # Process pipeline
    await document_service.process_document_pipeline(doc_id, test_db_session)

    # Delete
    del_res = await async_client.delete(f"/api/v1/documents/{doc_id}")
    assert del_res.status_code == 200
    assert del_res.json()["data"]["deleted"] is True

    # Check status now returns not found
    check_res = await async_client.get(f"/api/v1/documents/{doc_id}")
    assert check_res.json()["success"] is False
    assert check_res.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_document_retry_flow(async_client: AsyncClient, test_db_session):
    """
    Test 9: Retry mechanism for failed processing.
    """
    pdf_bytes = create_sample_pdf(num_pages=1, text="Retryable document test.")
    files = {"file": ("retry.pdf", pdf_bytes, "application/pdf")}
    up_res = await async_client.post("/api/v1/documents/upload", files=files)
    doc_id = uuid.UUID(up_res.json()["data"]["document_id"])

    # Simulate recoverable failure
    doc = await test_db_session.get(Document, doc_id)
    doc.status = "FAILED"
    doc.is_retryable = True
    doc.error_code = "SIMULATED_WORKER_ERROR"
    doc.error_message = "Worker timeout"
    await test_db_session.commit()

    # Call retry endpoint
    retry_res = await async_client.post(f"/api/v1/documents/{doc_id}/retry")
    assert retry_res.status_code == 200
    assert retry_res.json()["data"]["status"] == "UPLOADED"


@pytest.mark.asyncio
async def test_cleanup_expired_documents(test_db_session):
    """
    Test 10: Automatic cleanup of documents past their 24h TTL.
    """
    now = datetime.now(timezone.utc)
    # Create expired document
    expired_doc = Document(
        id=uuid.uuid4(),
        original_filename="expired.pdf",
        storage_key="documents/expired/original/expired.pdf",
        mime_type="application/pdf",
        file_size=100,
        sha256_hash="dummyhash",
        status="READY",
        page_count=1,
        ocr_required=False,
        created_at=now - timedelta(hours=25),
        updated_at=now - timedelta(hours=25),
        expires_at=now - timedelta(hours=1),
        is_retryable=False
    )
    test_db_session.add(expired_doc)
    await test_db_session.commit()

    # Run cleanup
    purged = await document_service.cleanup_expired_documents(test_db_session)
    assert purged >= 1
