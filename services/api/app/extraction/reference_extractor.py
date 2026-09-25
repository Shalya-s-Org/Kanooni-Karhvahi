import re
from typing import List
from app.extraction.base import BaseEntityExtractor
from app.extraction.models import RawExtractedEntity


class ReferenceExtractor(BaseEntityExtractor):
    """
    Deterministic extractor for legal and administrative reference numbers.
    Detects FIR numbers, Case/Suit numbers, Notice reference codes, and Agreement IDs.
    Rejects arbitrary standalone digits or numbers lacking contextual indicators.
    """

    PATTERNS = [
        # FIR Numbers: "FIR No. 123/2024", "FIR Number: 45/2023", "FIR No: 789/2022"
        (
            re.compile(r"\b(?:fir\s*(?:no\.?|number|num)\s*[:\-–]?\s*)(?P<id>[A-Za-z0-9\/\-_]+(?:\s+of\s+\d{4})?)", re.IGNORECASE),
            "REFERENCE_NUMBER",
            "FIR_NUMBER"
        ),

        # Case / Suit / Petition Numbers: "Civil Suit No. 142/2023", "W.P.(C) No. 1024/2022", "Criminal Appeal No. 55 of 2021"
        (
            re.compile(r"\b(?P<prefix>(?:civil\s+suit|criminal\s+case|writ\s+petition|special\s+leave\s+petition|slp|c\.?a\.?|w\.?p\.?(?:\([A-Za-z]+\))?|suit|case|petition)\s*(?:no\.?|number)?\s*[:\-–]?\s*)(?P<id>[A-Za-z0-9\/\-_]+(?:\s+of\s+\d{4})?)", re.IGNORECASE),
            "CASE_NUMBER",
            "CASE_NUMBER"
        ),

        # Notice References: "Notice Ref: IT/2024/099", "Ref No. 2024/NOV/45", "Reference No: ABC-123"
        (
            re.compile(r"\b(?P<prefix>(?:notice\s+ref(?:erence)?|ref(?:erence)?\s*(?:no\.?|number)?)\s*[:\-–]?\s*)(?P<id>[A-Za-z0-9\/\-_]+)", re.IGNORECASE),
            "REFERENCE_NUMBER",
            "NOTICE_REFERENCE"
        ),

        # Agreement / Contract IDs: "Agreement No: AG-2024-88", "Contract Ref: C/2024/1"
        (
            re.compile(r"\b(?P<prefix>(?:agreement|contract|loan\s+account|policy)\s*(?:no\.?|number|id|ref)\s*[:\-–]?\s*)(?P<id>[A-Za-z0-9\/\-_]+)", re.IGNORECASE),
            "REFERENCE_NUMBER",
            "AGREEMENT_REFERENCE"
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

        for pattern, ent_type, sub_type in self.PATTERNS:
            for m in pattern.finditer(text):
                raw_val = m.group(0).strip()
                ref_id = m.group("id").strip().rstrip(".,;")

                # Reject purely short or empty matches
                if len(ref_id) < 2 or ref_id.lower() in ["the", "dated", "under", "is", "for", "to"]:
                    continue

                span = (m.start(), m.end())
                if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
                    continue

                seen_spans.add(span)
                seen_values.add(ref_id.lower())

                ctx = self._extract_context(text, m.start(), m.end())

                entities.append(
                    RawExtractedEntity(
                        entity_type=ent_type,
                        value=raw_val,
                        normalized_value=ref_id,
                        source_text=ctx.strip(),
                        start_offset=m.start(),
                        end_offset=m.end(),
                        confidence=0.93,
                        metadata={"reference_type": sub_type, "identifier": ref_id}
                    )
                )

        return entities
