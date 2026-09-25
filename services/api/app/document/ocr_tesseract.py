import os
import shutil
import asyncio
from typing import Optional
from PIL import Image
import pytesseract
from app.document.ocr_base import OCRProvider, OCRResult, OCRDependencyMissingError
from app.core.logging import logger


class TesseractOCRProvider(OCRProvider):
    """
    Local Tesseract OCR engine integration with host environment verification.
    """

    def __init__(self, tesseract_cmd: Optional[str] = None):
        self.cmd = tesseract_cmd or self._detect_executable()
        if self.cmd:
            pytesseract.pytesseract.tesseract_cmd = self.cmd

    def _detect_executable(self) -> Optional[str]:
        # 1. System PATH
        which_path = shutil.which("tesseract")
        if which_path:
            return which_path

        # 2. Standard Windows installation locations
        win_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
        ]
        for p in win_paths:
            if os.path.exists(p):
                return p

        return None

    def is_available(self) -> bool:
        if not self.cmd:
            return False
        try:
            version = pytesseract.get_tesseract_version()
            return bool(version)
        except Exception:
            return False

    async def extract_from_image(self, image_path: str) -> OCRResult:
        if not self.is_available():
            raise OCRDependencyMissingError(
                "Tesseract OCR is not installed or not in PATH on this system. "
                "Please install Tesseract-OCR or configure OCR_PROVIDER=mock for development."
            )

        # Run CPU-bound pytesseract in asyncio thread pool
        def _process() -> OCRResult:
            with Image.open(image_path) as img:
                width, height = img.size
                text = pytesseract.image_to_string(img)
                # Attempt to get data/confidence
                try:
                    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                    confidences = [int(c) for c in data.get("conf", []) if str(c).isdigit() and int(c) >= 0]
                    avg_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.85
                except Exception:
                    avg_conf = 0.80

                return OCRResult(
                    text=text.strip(),
                    confidence=round(avg_conf, 2),
                    width=width,
                    height=height
                )

        return await asyncio.to_thread(_process)
