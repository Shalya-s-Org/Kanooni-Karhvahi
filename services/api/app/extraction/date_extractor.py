import re
from datetime import datetime
from typing import List, Optional, Tuple
from app.extraction.base import BaseEntityExtractor
from app.extraction.models import RawExtractedEntity

MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12
}


class DateExtractor(BaseEntityExtractor):
    """
    Deterministic extractor for calendar dates and legal deadlines.
    Extracts dates across various Indian and international notations,
    normalizes to ISO format, and classifies semantic type based on contextual clues.
    """

    # 1. 15/10/2026, 15-10-2026, 15.10.2026
    P_NUMERIC = re.compile(
        r"\b(?P<day>[0-3]?\d)[/\.-](?P<month>[0-1]?\d)[/\.-](?P<year>19\d\d|20\d\d)\b"
    )

    # 2. 2026-10-15 (ISO format)
    P_ISO = re.compile(
        r"\b(?P<year>19\d\d|20\d\d)[/\.-](?P<month>[0-1]?\d)[/\.-](?P<day>[0-3]?\d)\b"
    )

    # 3. 15 October 2026, 15th October 2026, 15-Oct-2026
    P_TEXTUAL_DAY_FIRST = re.compile(
        r"\b(?P<day>[0-3]?\d)(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<month>january|february|march|april|may|june|july|august|september|sept|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)[,\.\s-]+(?P<year>19\d\d|20\d\d)\b",
        re.IGNORECASE
    )

    # 4. October 15, 2026, Oct 15th, 2026
    P_TEXTUAL_MONTH_FIRST = re.compile(
        r"\b(?P<month>january|february|march|april|may|june|july|august|september|sept|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\s+(?P<day>[0-3]?\d)(?:st|nd|rd|th)?[,\.\s-]+(?P<year>19\d\d|20\d\d)\b",
        re.IGNORECASE
    )

    # 5. Relative deadline: "within 15 days", "within 30 days of receipt"
    P_RELATIVE_DEADLINE = re.compile(
        r"\bwithin\s+(?P<num>\d+|fifteen|thirty|seven|fourteen|twenty|sixty|ninety)\s+days?(?:\s+(?:from|of)\s+[^,\.\n]+)?",
        re.IGNORECASE
    )

    SEMANTIC_CLUES = {
        "DEADLINE": [
            r"\bon\s+or\s+before\b",
            r"\bno\s+later\s+than\b",
            r"\bdeadline\b",
            r"\breply\s+within\b",
            r"\bdue\s+date\b",
            r"\bfail\s+not\b",
            r"\bcompliance\s+(?:by|before)\b",
            r"\blast\s+date\b",
            r"\bwithin\s+\d+\s+days\b"
        ],
        "DOCUMENT_DATE": [
            r"\bdated\s+(?:this\s+)?\b",
            r"\bdate\s+of\s+agreement\b",
            r"\bexecuted\s+on\b",
            r"\bmade\s+on\s+this\b",
            r"\bentered\s+into\s+on\b"
        ],
        "ISSUE_DATE": [
            r"\bissued\s+on\b",
            r"\bdate\s+of\s+issue\b",
            r"\bdate\s+of\s+notice\b"
        ],
        "HEARING_DATE": [
            r"\b(?:next\s+)?date\s+of\s+hearing\b",
            r"\bhearing\s+on\b",
            r"\bappear\s+on\b",
            r"\bfixed\s+for\b",
            r"\blisted\s+on\b",
            r"\bbefore\s+the\s+court\s+on\b"
        ],
        "PAYMENT_DATE": [
            r"\bpayable\s+on\b",
            r"\bpay\s+on\s+or\s+before\b",
            r"\brepayment\s+date\b",
            r"\bdue\s+on\b"
        ],
        "EFFECTIVE_DATE": [
            r"\beffective\s+date\b",
            r"\bcommencing\s+from\b",
            r"\bwith\s+effect\s+from\b",
            r"\bw\.e\.f\.\b"
        ],
        "EXPIRY_DATE": [
            r"\bexpiry\s+date\b",
            r"\bexpires\s+on\b",
            r"\bvalid\s+(?:up\s+to|till)\b",
            r"\btermination\s+date\b"
        ]
    }

    def _determine_semantic_type(self, text: str, start: int, end: int) -> Tuple[str, float]:
        """
        Determines the semantic date type from the immediate sentence or preceding/following words.
        """
        pre_ctx = text[max(0, start - 45):start].lower()
        post_ctx = text[end:min(len(text), end + 45)].lower()
        full_ctx = text[max(0, start - 45):min(len(text), end + 45)].lower()

        # Check immediate preceding context first (strongest indicator)
        if re.search(r"\b(?:dated\s*(?:this)?|date\s+of\s+(?:the\s+)?agreement|executed\s+on|made\s+on)\b", pre_ctx):
            return "DOCUMENT_DATE", 0.94

        if re.search(r"\b(?:date\s+of\s+hearing|hearing\s+on|appear\s+on|fixed\s+for|listed\s+on)\b", pre_ctx):
            return "HEARING_DATE", 0.94

        if re.search(r"\b(?:on\s+or\s+before|no\s+later\s+than|deadline|due\s+date|fail\s+not|last\s+date|compliance\s+by)\b", pre_ctx):
            return "DEADLINE", 0.94

        if re.search(r"\b(?:issued\s+on|date\s+of\s+issue|date\s+of\s+notice)\b", pre_ctx):
            return "ISSUE_DATE", 0.92

        if re.search(r"\b(?:effective\s+date|commencing\s+from|with\s+effect\s+from|w\.e\.f\.)\b", pre_ctx):
            return "EFFECTIVE_DATE", 0.92

        if re.search(r"\b(?:payable\s+on|repayment\s+date|due\s+on)\b", pre_ctx):
            return "PAYMENT_DATE", 0.92

        if re.search(r"\b(?:expiry\s+date|expires\s+on|valid\s+(?:up\s+to|till)|termination\s+date)\b", full_ctx):
            return "EXPIRY_DATE", 0.92

        # Broader sentence fallback
        for sem_type, patterns in self.SEMANTIC_CLUES.items():
            for p in patterns:
                if re.search(p, full_ctx):
                    return sem_type, 0.90

        return "OTHER_DATE", 0.85

    def _extract_context(self, text: str, start: int, end: int, window: int = 70) -> str:
        s = max(0, start - window)
        e = min(len(text), end + window)
        return text[s:e]


    def _normalize_date(self, day: int, month: int, year: int) -> Optional[str]:
        try:
            dt = datetime(year, month, day)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None

    def extract(self, text: str, page_number: int) -> List[RawExtractedEntity]:
        entities: List[RawExtractedEntity] = []
        seen_spans = set()

        # Check relative deadlines first
        for m in self.P_RELATIVE_DEADLINE.finditer(text):
            val = m.group(0).strip()
            span = (m.start(), m.end())
            seen_spans.add(span)
            ctx = self._extract_context(text, m.start(), m.end())
            entities.append(
                RawExtractedEntity(
                    entity_type="DEADLINE",
                    value=val,
                    normalized_value=val,
                    source_text=ctx.strip(),
                    start_offset=m.start(),
                    end_offset=m.end(),
                    confidence=0.92,
                    metadata={"date_type": "DEADLINE", "is_relative": True}
                )
            )

        # 1. Textual Month First: "October 15, 2026"
        for m in self.P_TEXTUAL_MONTH_FIRST.finditer(text):
            span = (m.start(), m.end())
            if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
                continue
            seen_spans.add(span)

            month_str = m.group("month").lower()
            month = MONTH_MAP.get(month_str)
            day = int(m.group("day"))
            year = int(m.group("year"))

            if not month or not (1 <= day <= 31):
                continue

            iso_norm = self._normalize_date(day, month, year)
            if not iso_norm:
                continue

            ctx = self._extract_context(text, m.start(), m.end())
            sem_type, conf = self._determine_semantic_type(text, m.start(), m.end())
            entity_type = "DEADLINE" if sem_type == "DEADLINE" else "DATE"

            entities.append(
                RawExtractedEntity(
                    entity_type=entity_type,
                    value=m.group(0),
                    normalized_value=iso_norm,
                    source_text=ctx.strip(),
                    start_offset=m.start(),
                    end_offset=m.end(),
                    confidence=conf,
                    metadata={"date_type": sem_type}
                )
            )

        # 2. Textual Day First: "15 October 2026", "15th October 2026"
        for m in self.P_TEXTUAL_DAY_FIRST.finditer(text):
            span = (m.start(), m.end())
            if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
                continue
            seen_spans.add(span)

            month_str = m.group("month").lower()
            month = MONTH_MAP.get(month_str)
            day = int(m.group("day"))
            year = int(m.group("year"))

            if not month or not (1 <= day <= 31):
                continue

            iso_norm = self._normalize_date(day, month, year)
            if not iso_norm:
                continue

            ctx = self._extract_context(text, m.start(), m.end())
            sem_type, conf = self._determine_semantic_type(text, m.start(), m.end())
            entity_type = "DEADLINE" if sem_type == "DEADLINE" else "DATE"

            entities.append(
                RawExtractedEntity(
                    entity_type=entity_type,
                    value=m.group(0),
                    normalized_value=iso_norm,
                    source_text=ctx.strip(),
                    start_offset=m.start(),
                    end_offset=m.end(),
                    confidence=conf,
                    metadata={"date_type": sem_type}
                )
            )

        # 3. Numeric: 15/10/2026 or 15-10-2026
        for m in self.P_NUMERIC.finditer(text):
            span = (m.start(), m.end())
            if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
                continue
            seen_spans.add(span)

            day = int(m.group("day"))
            month = int(m.group("month"))
            year = int(m.group("year"))

            # Disambiguate if day/month inverted or invalid
            if month > 12 and day <= 12:
                day, month = month, day

            iso_norm = self._normalize_date(day, month, year)
            if not iso_norm:
                continue

            ctx = self._extract_context(text, m.start(), m.end())
            sem_type, conf = self._determine_semantic_type(text, m.start(), m.end())
            entity_type = "DEADLINE" if sem_type == "DEADLINE" else "DATE"

            entities.append(
                RawExtractedEntity(
                    entity_type=entity_type,
                    value=m.group(0),
                    normalized_value=iso_norm,
                    source_text=ctx.strip(),
                    start_offset=m.start(),
                    end_offset=m.end(),
                    confidence=conf,
                    metadata={"date_type": sem_type}
                )
            )

        # 4. ISO: 2026-10-15
        for m in self.P_ISO.finditer(text):
            span = (m.start(), m.end())
            if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
                continue
            seen_spans.add(span)

            year = int(m.group("year"))
            month = int(m.group("month"))
            day = int(m.group("day"))

            iso_norm = self._normalize_date(day, month, year)
            if not iso_norm:
                continue

            ctx = self._extract_context(text, m.start(), m.end())
            sem_type, conf = self._determine_semantic_type(text, m.start(), m.end())
            entity_type = "DEADLINE" if sem_type == "DEADLINE" else "DATE"

            entities.append(
                RawExtractedEntity(
                    entity_type=entity_type,
                    value=m.group(0),
                    normalized_value=iso_norm,
                    source_text=ctx.strip(),
                    start_offset=m.start(),
                    end_offset=m.end(),
                    confidence=conf,
                    metadata={"date_type": sem_type}
                )
            )

        return entities
