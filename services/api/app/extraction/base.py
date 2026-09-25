from abc import ABC, abstractmethod
from typing import List
from app.extraction.models import RawExtractedEntity


class BaseEntityExtractor(ABC):
    """
    Interface for modular entity extractors.
    Each extractor handles a specific domain (dates, amounts, parties, etc.)
    and returns traceable RawExtractedEntity items.
    """

    @abstractmethod
    def extract(self, text: str, page_number: int) -> List[RawExtractedEntity]:
        """
        Extract entities from the provided page text.
        :param text: Full text of the page
        :param page_number: 1-indexed page number
        :return: List of RawExtractedEntity
        """
        pass
