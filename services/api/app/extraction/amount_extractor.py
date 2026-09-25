import re
from typing import List, Tuple
from app.extraction.base import BaseEntityExtractor
from app.extraction.models import RawExtractedEntity


class AmountExtractor(BaseEntityExtractor):
    """
    Deterministic extractor for monetary amounts in Indian legal documents.
    Supports Rupee symbol (₹), Rs., INR, Lakhs, Crores, and paise decimals.
    Normalizes to numeric float/int, assigns currency INR, and detects semantic amount type.
    """

    # 1. Standard currency prefix: ₹50,000, Rs. 1,25,000.50, INR 5,00,000/-
    P_PREFIXED_AMOUNT = re.compile(
        r"(?P<curr>₹|rs\.?|inr)\s*(?P<num>\d{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\s*(?:/-\s*|\b)?",
        re.IGNORECASE
    )

    # 2. Words like: Rs. 5 Lakhs, 2.5 Crore, INR 10 Lakh
    P_LAKH_CRORE = re.compile(
        r"(?:(?P<curr>₹|rs\.?|inr)\s*)?(?P<num>\d+(?:\.\d{1,2})?)\s*(?P<unit>lakhs?|crores?|cr\.?|lac)\b",
        re.IGNORECASE
    )

    AMOUNT_TYPE_CLUES = {
        "PENALTY": [r"\bpenalt(?:y|ies)\b", r"\bpenal\b"],
        "FINE": [r"\bfine\b"],
        "COMPENSATION": [r"\bcompensation\b", r"\balimony\b", r"\bmaintenance\b"],
        "CONSIDERATION": [r"\bconsideration\b", r"\bsale\s+price\b", r"\bpurchase\s+price\b"],
        "SALARY": [r"\bsalary\b", r"\bremuneration\b", r"\bctc\b", r"\bstipend\b", r"\bwages\b"],
        "RENT": [r"\brent\b", r"\brental\b", r"\blease\s+rent\b"],
        "LOAN_AMOUNT": [r"\bloan\s+amount\b", r"\bprincipal\s+amount\b", r"\bsanctioned\s+amount\b", r"\bborrowed\b"],
        "SECURITY_DEPOSIT": [r"\bsecurity\s+deposit\b", r"\bearnest\s+money\b", r"\badvance\b"],
        "FEE": [r"\bfee\b", r"\bprofessional\s+fee\b", r"\bcharges\b", r"\bcourt\s+fee\b"],
        "DAMAGES": [r"\bdamages\b", r"\blosses\b"]
    }

    def _determine_amount_type(self, context: str) -> Tuple[str, float]:
        lower_ctx = context.lower()
        for amt_type, patterns in self.AMOUNT_TYPE_CLUES.items():
            for p in patterns:
                if re.search(p, lower_ctx):
                    return amt_type, 0.95
        return "UNKNOWN", 0.90

    def _parse_numeric(self, num_str: str) -> float:
        cleaned = num_str.replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def _extract_context(self, text: str, start: int, end: int, window: int = 70) -> str:
        s = max(0, start - window)
        e = min(len(text), end + window)
        return text[s:e]

    def extract(self, text: str, page_number: int) -> List[RawExtractedEntity]:
        entities: List[RawExtractedEntity] = []
        seen_spans = set()

        # 1. Lakh / Crore patterns
        for m in self.P_LAKH_CRORE.finditer(text):
            val = m.group(0).strip()
            # If no currency symbol and unit isn't explicitly tied, require context sanity
            curr_str = m.group("curr")
            num = float(m.group("num"))
            unit = m.group("unit").lower()

            multiplier = 100000.0 if "lakh" in unit or "lac" in unit else 10000000.0
            norm_num = num * multiplier

            span = (m.start(), m.end())
            seen_spans.add(span)

            ctx = self._extract_context(text, m.start(), m.end())
            amt_type, conf = self._determine_amount_type(ctx)

            # If no currency prefix was attached, slightly reduce confidence
            if not curr_str:
                conf = max(0.75, conf - 0.10)

            # Format normalized value nicely: e.g. 250000 or 2500000
            norm_val_str = str(int(norm_num)) if norm_num.is_integer() else f"{norm_num:.2f}"

            entities.append(
                RawExtractedEntity(
                    entity_type="AMOUNT",
                    value=val,
                    normalized_value=norm_val_str,
                    source_text=ctx.strip(),
                    start_offset=m.start(),
                    end_offset=m.end(),
                    confidence=conf,
                    metadata={
                        "currency": "INR",
                        "numeric_value": norm_num,
                        "amount_type": amt_type,
                    }
                )
            )

        # 2. Prefixed amounts: ₹50,000, Rs. 1,25,000.50
        for m in self.P_PREFIXED_AMOUNT.finditer(text):
            span = (m.start(), m.end())
            if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
                continue
            seen_spans.add(span)

            val = m.group(0).strip()
            num_str = m.group("num")
            num_val = self._parse_numeric(num_str)
            if num_val <= 0:
                continue

            ctx = self._extract_context(text, m.start(), m.end())
            amt_type, conf = self._determine_amount_type(ctx)

            norm_val_str = str(int(num_val)) if num_val.is_integer() else f"{num_val:.2f}"

            entities.append(
                RawExtractedEntity(
                    entity_type="AMOUNT",
                    value=val,
                    normalized_value=norm_val_str,
                    source_text=ctx.strip(),
                    start_offset=m.start(),
                    end_offset=m.end(),
                    confidence=conf,
                    metadata={
                        "currency": "INR",
                        "numeric_value": num_val,
                        "amount_type": amt_type,
                    }
                )
            )

        return entities
