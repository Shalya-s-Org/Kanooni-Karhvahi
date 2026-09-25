import os
import io
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from PIL import Image
import fitz  # PyMuPDF
from app.document.ocr_base import OCRProvider
from app.document.storage import LocalDocumentStorage
from app.core.logging import logger


class ExtractedPageResult(BaseModel):
    page_number: int
    text: str
    ocr_used: bool
    ocr_confidence: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    image_storage_key: Optional[str] = None


class ExtractedDocumentResult(BaseModel):
    total_pages: int
    ocr_required: bool
    pages: List[ExtractedPageResult]


class DocumentExtractor:
    """
    Intelligent document parser for Indian legal documents.
    Prefers native digital text extraction and falls back to OCR on image/scanned pages.
    """

    def __init__(self, storage: LocalDocumentStorage, ocr_provider: OCRProvider):
        self.storage = storage
        self.ocr_provider = ocr_provider

    async def extract(
        self,
        document_id: UUID,
        file_path: str,
        mime_type: str
    ) -> ExtractedDocumentResult:
        """
        Dispatches file to appropriate extractor based on MIME type.
        """
        mime_clean = mime_type.lower()

        if mime_clean == "application/pdf":
            return await self._extract_pdf(document_id, file_path)
        elif mime_clean in ["image/jpeg", "image/png", "image/tiff", "image/jpg"]:
            return await self._extract_image(document_id, file_path)
        elif mime_clean == "text/plain":
            return await self._extract_plain_text(document_id, file_path)
        else:
            raise ValueError(f"Unsupported MIME type for extraction: {mime_type}")

    async def _extract_pdf(self, document_id: UUID, file_path: str) -> ExtractedDocumentResult:
        doc = fitz.open(file_path)
        total_pages = len(doc)
        pages_result: List[ExtractedPageResult] = []
        any_ocr_required = False

        self.storage.get_document_dir(document_id)

        for i, page in enumerate(doc):
            page_num = i + 1
            rect = page.rect
            page_width = int(rect.width)
            page_height = int(rect.height)

            # 1. Attempt native digital text extraction
            native_text = page.get_text("text").strip()

            # A page is considered digitally readable if it has substantive characters (>= 30 non-whitespace chars)
            if len(native_text) >= 30:
                pages_result.append(
                    ExtractedPageResult(
                        page_number=page_num,
                        text=native_text,
                        ocr_used=False,
                        ocr_confidence=None,
                        width=page_width,
                        height=page_height,
                        image_storage_key=None
                    )
                )
            else:
                # 2. Scanned page fallback: Render page to image and perform OCR
                any_ocr_required = True
                page_img_filename = f"page_{page_num}.png"
                page_storage_key = self.storage.generate_storage_key(document_id, "pages", page_img_filename)
                page_img_abs_path = self.storage.get_absolute_path(page_storage_key)

                # Render page at 150 DPI for optimal OCR balance
                pix = page.get_pixmap(dpi=150)
                pix.save(page_img_abs_path)

                # Perform OCR
                ocr_out = await self.ocr_provider.extract_from_image(page_img_abs_path)

                pages_result.append(
                    ExtractedPageResult(
                        page_number=page_num,
                        text=ocr_out.text,
                        ocr_used=True,
                        ocr_confidence=ocr_out.confidence,
                        width=page_width,
                        height=page_height,
                        image_storage_key=page_storage_key
                    )
                )

        doc.close()

        return ExtractedDocumentResult(
            total_pages=total_pages,
            ocr_required=any_ocr_required,
            pages=pages_result
        )

    async def _extract_image(self, document_id: UUID, file_path: str) -> ExtractedDocumentResult:
        with Image.open(file_path) as img:
            width, height = img.size

        # Run OCR on the image
        ocr_out = await self.ocr_provider.extract_from_image(file_path)

        # Store image reference as page 1
        page_storage_key = self.storage.generate_storage_key(document_id, "pages", "page_1.png")
        page_abs_path = self.storage.get_absolute_path(page_storage_key)
        os.makedirs(os.path.dirname(page_abs_path), exist_ok=True)
        if not os.path.exists(page_abs_path):
            with Image.open(file_path) as img:
                img.save(page_abs_path, format="PNG")

        return ExtractedDocumentResult(
            total_pages=1,
            ocr_required=True,
            pages=[
                ExtractedPageResult(
                    page_number=1,
                    text=ocr_out.text,
                    ocr_used=True,
                    ocr_confidence=ocr_out.confidence,
                    width=width,
                    height=height,
                    image_storage_key=page_storage_key
                )
            ]
        )

    async def _extract_plain_text(self, document_id: UUID, file_path: str) -> ExtractedDocumentResult:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        return ExtractedDocumentResult(
            total_pages=1,
            ocr_required=False,
            pages=[
                ExtractedPageResult(
                    page_number=1,
                    text=content.strip(),
                    ocr_used=False,
                    ocr_confidence=None,
                    width=None,
                    height=None,
                    image_storage_key=None
                )
            ]
        )
