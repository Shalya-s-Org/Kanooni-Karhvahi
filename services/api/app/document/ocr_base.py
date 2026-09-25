from abc import ABC, abstractmethod
from typing import Dict, Any, List


class OCRProvider(ABC):
    """
    Abstract Base Class for OCR engines.
    Isolates external engines (Tesseract, EasyOCR, Google Cloud Vision) from the core processing pipeline.
    """

    @abstractmethod
    async def extract_text(self, file_path: str) -> str:
        """
        Extracts raw plain text from an image or scanned PDF document.
        """
        pass

    @abstractmethod
    async def extract_layout(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extracts text blocks with bounding boxes and page numbers.
        """
        pass


class MockOCRProvider(OCRProvider):
    """
    Mock OCR provider for tests and local development.
    """

    async def extract_text(self, file_path: str) -> str:
        return "[MOCK OCR]: Simulated extracted text from legal document."

    async def extract_layout(self, file_path: str) -> List[Dict[str, Any]]:
        return [
            {
                "page": 1,
                "text": "[MOCK OCR BLOCK 1]: In the High Court of Judicature...",
                "bbox": [0, 0, 100, 100]
            }
        ]
