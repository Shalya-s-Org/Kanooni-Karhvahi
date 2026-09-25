import re
from typing import List
from app.extraction.base import BaseEntityExtractor
from app.extraction.models import RawExtractedEntity


class ContactExtractor(BaseEntityExtractor):
    """
    Deterministic extractor for contact details (Email addresses and Phone numbers)
    commonly present in legal notices and official correspondence.
    """

    P_EMAIL = re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
    )

    # Indian phone numbers: +91 9876543210, 09876543210, +91-11-23456789
    P_PHONE = re.compile(
        r"(?:(?:\+91[\-\s]?)|(?:\b0))?[6-9]\d{9}\b"
    )

    def _extract_context(self, text: str, start: int, end: int, window: int = 60) -> str:
        s = max(0, start - window)
        e = min(len(text), end + window)
        return text[s:e]

    def extract(self, text: str, page_number: int) -> List[RawExtractedEntity]:
        entities: List[RawExtractedEntity] = []

        # Emails
        for m in self.P_EMAIL.finditer(text):
            val = m.group(0).strip()
            ctx = self._extract_context(text, m.start(), m.end())
            entities.append(
                RawExtractedEntity(
                    entity_type="EMAIL",
                    value=val,
                    normalized_value=val.lower(),
                    source_text=ctx.strip(),
                    start_offset=m.start(),
                    end_offset=m.end(),
                    confidence=0.98,
                    metadata={"email": val.lower()}
                )
            )

        # Phone numbers
        for m in self.P_PHONE.finditer(text):
            val = m.group(0).strip()
            # Normalize digits only
            digits = re.sub(r"\D", "", val)
            if len(digits) >= 10:
                ctx = self._extract_context(text, m.start(), m.end())
                entities.append(
                    RawExtractedEntity(
                        entity_type="PHONE_NUMBER",
                        value=val,
                        normalized_value=digits[-10:],
                        source_text=ctx.strip(),
                        start_offset=m.start(),
                        end_offset=m.end(),
                        confidence=0.92,
                        metadata={"phone": digits}
                    )
                )

        return entities
