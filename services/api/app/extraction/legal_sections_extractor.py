import re
from typing import List
from app.extraction.base import BaseEntityExtractor
from app.extraction.models import RawExtractedEntity


class LegalSectionsExtractor(BaseEntityExtractor):
    """
    Deterministic extractor for textual references to statutory provisions, sections, articles, and rules.
    Detects patterns like:
      - Section 138 of Negotiable Instruments Act
      - Section 302, Section 420 IPC
      - Article 14, Article 21 of Constitution of India
      - Rule 5, Order XXXIX Rule 1 CPC
      - u/s 420/467/468 IPC
    Does NOT interpret legal meaning or applicability per Phase 3 specifications.
    """

    PATTERNS = [
        # Full phrase: "Section 138 of the Negotiable Instruments Act, 1881" or "Section 420 IPC"
        re.compile(
            r"\b(?:section|sec\.?)\s+(?P<sec>\d+[A-Za-z]?(?:\s*[\/\-]\s*\d+[A-Za-z]?)*)(?:\s+(?:read\s+with\s+section\s+\d+[A-Za-z]?))?(?:\s+(?:of\s+(?:the\s+)?|under\s+(?:the\s+)?|in\s+(?:the\s+)?)(?P<act>[A-Z][A-Za-z\s,\.-]+?(?:Act(?:\s*,\s*\d{4})?|Code(?:\s*,\s*\d{4})?|Rules(?:\s*,\s*\d{4})?|IPC|CrPC|CPC|BNS|BNSS)))?\b",
            re.IGNORECASE
        ),

        # u/s 420 / 468 IPC: "u/s 302/34 IPC", "U/S 138 NI Act"
        re.compile(
            r"\bu/s\s+(?P<sec>\d+[A-Za-z]?(?:\s*[\/\-]\s*\d+[A-Za-z]?)*)(?:\s+(?:read\s+with\s+\d+[A-Za-z]?))?(?:\s+(?P<act>IPC|CrPC|CPC|BNS|BNSS|NI\s+Act|[A-Z][A-Za-z\s]+Act))?\b",
            re.IGNORECASE
        ),

        # Constitutional Articles: "Article 14", "Article 21 of the Constitution of India", "Article 226"
        re.compile(
            r"\barticle\s+(?P<art>\d+[A-Za-z]?)(?:\s+(?:of\s+(?:the\s+)?)(?:constitution\s+(?:of\s+india)?))?\b",
            re.IGNORECASE
        ),

        # Rules / Orders: "Order XXXIX Rule 1", "Rule 5 of ..."
        re.compile(
            r"\b(?:order\s+[IVXLCDM]+\s+rule\s+\d+[A-Za-z]?|rule\s+\d+[A-Za-z]?(?:\s+(?:of|under)\s+[A-Z][A-Za-z\s]+Rules)?)\b",
            re.IGNORECASE
        ),
    ]

    def _extract_context(self, text: str, start: int, end: int, window: int = 70) -> str:
        s = max(0, start - window)
        e = min(len(text), end + window)
        return text[s:e]

    def extract(self, text: str, page_number: int) -> List[RawExtractedEntity]:
        entities: List[RawExtractedEntity] = []
        seen_spans = set()
        seen_values = set()

        for pattern in self.PATTERNS:
            for m in pattern.finditer(text):
                val = re.sub(r"\s+", " ", m.group(0)).strip()
                val = val.rstrip(".,;")

                if len(val) < 4 or val.lower() in seen_values:
                    continue

                span = (m.start(), m.end())
                if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
                    continue

                seen_spans.add(span)
                seen_values.add(val.lower())

                ctx = self._extract_context(text, m.start(), m.end())

                entities.append(
                    RawExtractedEntity(
                        entity_type="LEGAL_SECTION",
                        value=val,
                        normalized_value=val,
                        source_text=ctx.strip(),
                        start_offset=m.start(),
                        end_offset=m.end(),
                        confidence=0.94,
                        metadata={"raw_reference": val}
                    )
                )

        return entities
