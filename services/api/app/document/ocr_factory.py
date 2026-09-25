from typing import Optional
from app.core.config import settings
from app.core.logging import logger
from app.document.ocr_base import OCRProvider, MockOCRProvider
from app.document.ocr_tesseract import TesseractOCRProvider


def get_ocr_provider(provider_name: Optional[str] = None) -> OCRProvider:
    name = (provider_name or settings.OCR_PROVIDER).lower()

    if name == "tesseract":
        tess = TesseractOCRProvider()
        if tess.is_available():
            return tess
        logger.warning(
            "OCR_PROVIDER is configured as 'tesseract' but Tesseract binary was not found. "
            "Falling back to MockOCRProvider."
        )
        return MockOCRProvider()

    if name == "mock":
        return MockOCRProvider()

    logger.warning("Unknown OCR provider '%s'. Defaulting to MockOCRProvider.", name)
    return MockOCRProvider()
