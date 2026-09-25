from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class OCRResult(BaseModel):
    """
    Structured outcome of an OCR extraction on an image page.
    """
    text: str = Field(..., description="Extracted plain text")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Confidence metric")
    width: Optional[int] = Field(default=None, description="Image width")
    height: Optional[int] = Field(default=None, description="Image height")
    blocks: Optional[List[Dict[str, Any]]] = Field(default=None, description="Layout bounding boxes")


class OCRDependencyMissingError(RuntimeError):
    """
    Raised when an OCR engine (e.g. Tesseract) is not installed on the host system.
    """
    pass


class OCRProvider(ABC):
    """
    Abstract Base Class for OCR engines.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """
        Returns True if the underlying OCR engine is installed and ready.
        """
        pass

    @abstractmethod
    async def extract_from_image(self, image_path: str) -> OCRResult:
        """
        Runs OCR on an image file path and returns structured text and dimensions.
        """
        pass


class MockOCRProvider(OCRProvider):
    """
    Deterministic Mock OCR provider for automated testing and offline environments.
    """

    def __init__(self, simulated_text: str = "[MOCK OCR EXTRACTED TEXT]: In the High Court of Judicature at New Delhi..."):
        self.simulated_text = simulated_text

    def is_available(self) -> bool:
        return True

    async def extract_from_image(self, image_path: str) -> OCRResult:
        return OCRResult(
            text=self.simulated_text,
            confidence=0.95,
            width=2480,
            height=3508,
            blocks=[
                {"box": [100, 100, 500, 150], "text": "High Court of Judicature"}
            ]
        )
