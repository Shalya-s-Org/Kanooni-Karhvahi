import re
from typing import List
from app.extraction.base import BaseEntityExtractor
from app.extraction.models import RawExtractedEntity


class AuthoritiesExtractor(BaseEntityExtractor):
    """
    Deterministic extractor for public and institutional authorities in Indian legal documents.
    Detects police stations, courts, ministries, government departments, municipal bodies,
    tribunals, statutory authorities, and major banks.
    Preserves exact original spelling.
    """

    PATTERNS = [
        # Police Stations: "Police Station Connaught Place", "Police Station: Hauz Khas", "PS Sector 18 Noida"
        re.compile(r"\b(?:police\s+station|p\.?s\.?)\s*[:\-–]?\s+[A-Z][A-Za-z0-9\s,\.-]+?(?=[,\n;\.]|\s+(?:district|dist\.?|under|dated)|$)", re.IGNORECASE),

        # Courts: "High Court of Delhi", "Supreme Court of India", "Court of Chief Metropolitan Magistrate", "District & Sessions Court"
        re.compile(r"\b(?:in\s+the\s+)?(?:court\s+of\s+[A-Z][A-Za-z\s,\.-]+|high\s+court\s+of\s+[A-Z][A-Za-z\s]+|supreme\s+court\s+of\s+india|district\s+(?:&|and)?\s+sessions\s+court\s+[A-Z][A-Za-z\s]+|family\s+court\s+[A-Z][A-Za-z\s]+)\b", re.IGNORECASE),


        # Ministries & Departments: "Ministry of Finance", "Department of Revenue", "Income Tax Department", "Ministry of Corporate Affairs"
        re.compile(r"\b(?:ministry\s+of\s+[A-Z][A-Za-z\s&]+|department\s+of\s+[A-Z][A-Za-z\s&]+|income\s+tax\s+department|central\s+board\s+of\s+direct\s+taxes|cbdt|enforcement\s+directorate)\b", re.IGNORECASE),

        # Municipal Authorities: "Municipal Corporation of Delhi", "Bruhat Bengaluru Mahanagara Palike"
        re.compile(r"\b(?:municipal\s+corporation\s+of\s+[A-Z][A-Za-z\s]+|[A-Z][a-z]+\s+municipal\s+corporation|delhi\s+development\s+authority|dda)\b", re.IGNORECASE),

        # Tribunals: "National Company Law Tribunal", "NCLT", "Debt Recovery Tribunal", "DRT", "National Green Tribunal", "NGT", "Central Administrative Tribunal", "CAT"
        re.compile(r"\b(?:national\s+company\s+law\s+tribunal|debt\s+recovery\s+tribunal|national\s+green\s+tribunal|central\s+administrative\s+tribunal|consumer\s+disputes\s+redressal\s+commission|nclt|drt|ngt|cat|rera)\b", re.IGNORECASE),

        # Sub-Registrar / Government offices: "Office of the Sub-Registrar", "Collectorate Office"
        re.compile(r"\b(?:office\s+of\s+(?:the\s+)?)?(?:sub-registrar(?:\s+office)?|collectorate(?:\s+office)?|tehsildar(?:\s+office)?|competent\s+authority)\b", re.IGNORECASE),

        # Banks: "Reserve Bank of India", "State Bank of India", "Punjab National Bank", "HDFC Bank Ltd."
        re.compile(r"\b(?:reserve\s+bank\s+of\s+india|state\s+bank\s+of\s+india|punjab\s+national\s+bank|bank\s+of\s+baroda|canara\s+bank|hdfc\s+bank|icici\s+bank|axis\s+bank|kotak\s+mahindra\s+bank)\b", re.IGNORECASE),
    ]

    def _clean_val(self, val: str) -> str:
        cleaned = re.sub(r"\s+", " ", val).strip()
        cleaned = cleaned.lstrip("in the ").lstrip("In the ")
        return cleaned.rstrip(" ,;.")

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
                val = self._clean_val(m.group(0))
                if len(val) < 3 or val.lower() in seen_values:
                    continue

                span = (m.start(), m.end())
                if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
                    continue

                seen_spans.add(span)
                seen_values.add(val.lower())

                ctx = self._extract_context(text, m.start(), m.end())

                entities.append(
                    RawExtractedEntity(
                        entity_type="AUTHORITY",
                        value=val,
                        normalized_value=val,
                        source_text=ctx.strip(),
                        start_offset=m.start(),
                        end_offset=m.end(),
                        confidence=0.92,
                        metadata={"authority_name": val}
                    )
                )

        return entities
