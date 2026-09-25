from app.document.storage import DocumentStorageProvider, LocalDocumentStorage
from app.document.ocr_base import OCRProvider, MockOCRProvider

__all__ = [
    "DocumentStorageProvider",
    "LocalDocumentStorage",
    "OCRProvider",
    "MockOCRProvider",
]
