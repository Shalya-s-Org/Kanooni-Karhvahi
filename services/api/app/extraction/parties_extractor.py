import re
from typing import List, Tuple
from app.extraction.base import BaseEntityExtractor
from app.extraction.models import RawExtractedEntity


class PartiesExtractor(BaseEntityExtractor):
    """
    Deterministic extractor for legal parties and their declared legal roles.
    Matches explicit role prefixes (Complainant, Accused, Plaintiff, Defendant,
    Borrower, Lender, Employer, Employee, Landlord, Tenant, Petitioner, Respondent)
    and standard 'Between X and Y' agreements.
    Preserves exact name and role without guessing unstated relationships.
    """

    # 1. Direct role prefix: "Complainant: Ramesh Kumar", "Accused - Vikram Singh"
    # "Plaintiff: XYZ Ltd.", "Petitioner: ABC"
    P_ROLE_COLON = re.compile(
        r"\b(?P<role>complainant|accused|plaintiff|defendant|petitioner|respondent|employer|employee|borrower|lender|landlord|tenant|lessor|lessee|buyer|seller|vendor|purchaser)\s*[:\-–]\s*(?P<name>(?:(?:Mr\.|Mrs\.|Ms\.|Dr\.|Shri|Smt\.|M/s\.?)\s+)?[A-Z][A-Za-z0-9\.\s&,]+?)(?=[,\n;\.]|\s+(?:son\s+of|daughter\s+of|wife\s+of|s/o|d/o|w/o|residing\s+at|having\s+office|aged|r/o)|\b(?:versus|vs\.?)\b|$)",
        re.IGNORECASE
    )

    # 2. In title / cause title: "Ramesh Sharma ... Complainant", "ABC Corp ... Accused"
    P_NAME_THEN_ROLE = re.compile(
        r"(?:^|\n)\s*(?P<name>(?:(?:Mr\.|Mrs\.|Ms\.|Dr\.|Shri|Smt\.|M/s\.?)\s+)?[A-Z][A-Za-z\s\.\&]+?)\s*\.{3,}\s*(?P<role>complainant|accused|plaintiff|defendant|petitioner|respondent|appellant)",
        re.IGNORECASE | re.MULTILINE
    )

    # 3. Contract definition clauses:
    # "Between XYZ Ltd. (hereinafter referred to as the 'Employer')"
    # "AND ABC Sharma (hereinafter called 'Employee')"
    P_HEREINAFTER = re.compile(
        r"(?:between|and)\s+(?P<name>(?:(?:Mr\.|Mrs\.|Ms\.|Dr\.|Shri|Smt\.|M/s\.?)\s+)?[A-Z][A-Za-z0-9\.\s&,]+?)\s*\((?:hereinafter\s+(?:referred\s+to\s+as|called)\s+(?:the\s+)?[\"'](?P<role>[A-Za-z\s]+)[\"'])\)",
        re.IGNORECASE
    )

    # 4. Standalone honorific named party: "Shri Rajesh Kumar", "M/s Alpha Enterprises"
    P_HONORIFIC_NAME = re.compile(
        r"\b(?P<prefix>Shri|Smt\.|M/s\.?|Mr\.|Mrs\.|Dr\.)\s+(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b"
    )

    def _clean_name(self, raw_name: str) -> str:
        cleaned = re.sub(r"\s+", " ", raw_name).strip()
        cleaned = cleaned.rstrip(",;:-.")
        return cleaned

    def _extract_context(self, text: str, start: int, end: int, window: int = 70) -> str:
        s = max(0, start - window)
        e = min(len(text), end + window)
        return text[s:e]

    def _infer_entity_type(self, name: str) -> str:
        lower = name.lower()
        if any(corp in lower for corp in ["ltd", "limited", "pvt", "corp", "inc", "m/s", "company", "bank", "technologies", "solutions"]):
            return "ORGANIZATION"
        return "PERSON"

    def extract(self, text: str, page_number: int) -> List[RawExtractedEntity]:
        entities: List[RawExtractedEntity] = []
        seen_spans = set()
        seen_names = set()

        # 1. P_ROLE_COLON
        for m in self.P_ROLE_COLON.finditer(text):
            raw_name = m.group("name")
            cleaned_name = self._clean_name(raw_name)
            role = m.group("role").upper().strip()

            if len(cleaned_name) < 3 or cleaned_name.lower() in ["the", "an", "a", "notice", "order"]:
                continue

            span = (m.start("name"), m.end("name"))
            seen_spans.add(span)
            seen_names.add(cleaned_name.lower())

            ctx = self._extract_context(text, m.start(), m.end())
            ent_type = self._infer_entity_type(cleaned_name)

            entities.append(
                RawExtractedEntity(
                    entity_type=ent_type,
                    value=cleaned_name,
                    normalized_value=cleaned_name,
                    source_text=ctx.strip(),
                    start_offset=m.start("name"),
                    end_offset=m.end("name"),
                    confidence=0.92,
                    metadata={"role": role}
                )
            )

        # 2. P_HEREINAFTER
        for m in self.P_HEREINAFTER.finditer(text):
            raw_name = m.group("name")
            cleaned_name = self._clean_name(raw_name)
            role = m.group("role").upper().strip()

            if len(cleaned_name) < 3 or cleaned_name.lower() in seen_names:
                continue

            span = (m.start("name"), m.end("name"))
            seen_spans.add(span)
            seen_names.add(cleaned_name.lower())

            ctx = self._extract_context(text, m.start(), m.end())
            ent_type = self._infer_entity_type(cleaned_name)

            entities.append(
                RawExtractedEntity(
                    entity_type=ent_type,
                    value=cleaned_name,
                    normalized_value=cleaned_name,
                    source_text=ctx.strip(),
                    start_offset=m.start("name"),
                    end_offset=m.end("name"),
                    confidence=0.94,
                    metadata={"role": role}
                )
            )

        # 3. P_NAME_THEN_ROLE
        for m in self.P_NAME_THEN_ROLE.finditer(text):
            raw_name = m.group("name")
            cleaned_name = self._clean_name(raw_name)
            role = m.group("role").upper().strip()

            if len(cleaned_name) < 3 or cleaned_name.lower() in seen_names:
                continue

            span = (m.start("name"), m.end("name"))
            seen_spans.add(span)
            seen_names.add(cleaned_name.lower())

            ctx = self._extract_context(text, m.start(), m.end())
            ent_type = self._infer_entity_type(cleaned_name)

            entities.append(
                RawExtractedEntity(
                    entity_type=ent_type,
                    value=cleaned_name,
                    normalized_value=cleaned_name,
                    source_text=ctx.strip(),
                    start_offset=m.start("name"),
                    end_offset=m.end("name"),
                    confidence=0.90,
                    metadata={"role": role}
                )
            )

        # 4. Standalone honorific named party without explicit legal role
        for m in self.P_HONORIFIC_NAME.finditer(text):
            full_val = self._clean_name(m.group(0))
            if full_val.lower() in seen_names:
                continue
            span = (m.start(), m.end())
            if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
                continue

            seen_spans.add(span)
            seen_names.add(full_val.lower())
            ctx = self._extract_context(text, m.start(), m.end())
            ent_type = self._infer_entity_type(full_val)

            # Per specification: "Do not automatically classify a person's legal role unless the document explicitly supports it."
            entities.append(
                RawExtractedEntity(
                    entity_type=ent_type,
                    value=full_val,
                    normalized_value=full_val,
                    source_text=ctx.strip(),
                    start_offset=m.start(),
                    end_offset=m.end(),
                    confidence=0.82,
                    metadata={"role": "PARTY"}
                )
            )

        return entities
