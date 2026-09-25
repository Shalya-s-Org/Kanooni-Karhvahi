from abc import ABC, abstractmethod
from typing import List, Sequence, Tuple
from pydantic import BaseModel, Field
from app.classification.enums import DocumentType


class ClassificationEvidence(BaseModel):
    page: int = Field(..., ge=1, description="1-indexed source page number")
    text: str = Field(..., description="Excerpt or snippet demonstrating category indicators")


class DocumentClassificationResult(BaseModel):
    document_type: str = Field(..., description="Classified broad document type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    evidence: List[ClassificationEvidence] = Field(default_factory=list, description="Traceable evidence items")


class BaseDocumentClassifier(ABC):
    """
    Interface for legal document classification strategies (deterministic rule-based or model-assisted).
    """

    @abstractmethod
    async def classify(
        self,
        pages: Sequence[Tuple[int, str]],
        filename: str = ""
    ) -> DocumentClassificationResult:
        """
        Classifies document text across pages.
        :param pages: Sequence of (page_number, extracted_text)
        :param filename: Optional document filename for heuristic hint
        :return: DocumentClassificationResult with category, confidence, and traceable evidence
        """
        pass
