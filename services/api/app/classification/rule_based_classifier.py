import re
from typing import Dict, List, Sequence, Tuple
from app.classification.enums import DocumentType
from app.classification.base import (
    BaseDocumentClassifier,
    ClassificationEvidence,
    DocumentClassificationResult,
)


class RuleBasedDocumentClassifier(BaseDocumentClassifier):
    """
    Deterministic rule-based baseline legal document classifier.
    Examines structural headers, terminology patterns, and context indicators.
    Collects exact evidence snippets and assigns calibrated confidence.
    """

    # Category indicator definitions: (strong_patterns, regular_patterns)
    CATEGORY_RULES: Dict[DocumentType, Dict[str, List[re.Pattern]]] = {
        DocumentType.FIR: {
            "strong": [
                re.compile(r"\bfirst\s+information\s+report\b", re.IGNORECASE),
                re.compile(r"\bfir\s*(?:no\.?|number)\b", re.IGNORECASE),
                re.compile(r"\bpolice\s+station\b", re.IGNORECASE),
            ],
            "regular": [
                re.compile(r"\bcomplainant\b", re.IGNORECASE),
                re.compile(r"\baccused\b", re.IGNORECASE),
                re.compile(r"\bdate\s+of\s+occurrence\b", re.IGNORECASE),
                re.compile(r"\bu/s\s+\d+", re.IGNORECASE),
                re.compile(r"\bsections?\s+of\s+law\b", re.IGNORECASE),
                re.compile(r"\bipc\b|\bindian\s+penal\s+code\b|\bbharatiya\s+nyaya\s+sanhita\b", re.IGNORECASE),
                re.compile(r"\bcognizable\b", re.IGNORECASE),
            ],
        },
        DocumentType.LEGAL_NOTICE: {
            "strong": [
                re.compile(r"\blegal\s+notice\b", re.IGNORECASE),
                re.compile(r"\bunder\s+instructions\s+(?:from|of)\s+my\s+client\b", re.IGNORECASE),
                re.compile(r"\bnotice\s+under\s+section\b", re.IGNORECASE),
                re.compile(r"\bstatutory\s+notice\b", re.IGNORECASE),
                re.compile(r"\bdemand\s+notice\b", re.IGNORECASE),
            ],
            "regular": [
                re.compile(r"\badvocate\b", re.IGNORECASE),
                re.compile(r"\bwithout\s+prejudice\b", re.IGNORECASE),
                re.compile(r"\bhereby\s+call\s+upon\s+you\b", re.IGNORECASE),
                re.compile(r"\bfailing\s+which\s+(?:my\s+client|legal\s+action)\b", re.IGNORECASE),
                re.compile(r"\bnoticee\b", re.IGNORECASE),
                re.compile(r"\bnotice\s+period\b", re.IGNORECASE),
                re.compile(r"\breply\s+within\s+\d+\s+days\b", re.IGNORECASE),
            ],
        },
        DocumentType.GOVERNMENT_NOTICE: {
            "strong": [
                re.compile(r"\bgovernment\s+of\s+(?:india|[A-Z][a-z]+)\b", re.IGNORECASE),
                re.compile(r"\bshow\s+cause\s+notice\b", re.IGNORECASE),
                re.compile(r"\boffice\s+memorandum\b", re.IGNORECASE),
                re.compile(r"\bpublic\s+notice\b", re.IGNORECASE),
                re.compile(r"\bgazette\s+of\s+india\b", re.IGNORECASE),
            ],
            "regular": [
                re.compile(r"\bministry\s+of\b", re.IGNORECASE),
                re.compile(r"\bdepartment\s+of\b", re.IGNORECASE),
                re.compile(r"\bmunicipal\s+corporation\b", re.IGNORECASE),
                re.compile(r"\bcompetent\s+authority\b", re.IGNORECASE),
                re.compile(r"\bcompliance\b", re.IGNORECASE),
                re.compile(r"\breference\s+no\.?\b|\bref\s+no\.?\b", re.IGNORECASE),
                re.compile(r"\border\s+under\s+section\b", re.IGNORECASE),
            ],
        },
        DocumentType.CONTRACT: {
            "strong": [
                re.compile(r"\b(?:this\s+)?agreement\s+(?:is\s+)?entered\s+into\b", re.IGNORECASE),
                re.compile(r"\bparty\s+of\s+the\s+(?:first|second)\s+part\b", re.IGNORECASE),
                re.compile(r"\bin\s+witness\s+whereof\b", re.IGNORECASE),
                re.compile(r"\bcommercial\s+agreement\b", re.IGNORECASE),
            ],
            "regular": [
                re.compile(r"\bwhereas\b", re.IGNORECASE),
                re.compile(r"\bnow\s+therefore\b", re.IGNORECASE),
                re.compile(r"\bconsideration\b", re.IGNORECASE),
                re.compile(r"\bmutual\s+covenants\b", re.IGNORECASE),
                re.compile(r"\bterms\s+and\s+conditions\b", re.IGNORECASE),
                re.compile(r"\bseverability\b", re.IGNORECASE),
                re.compile(r"\bforce\s+majeure\b", re.IGNORECASE),
                re.compile(r"\bgoverning\s+law\b", re.IGNORECASE),
                re.compile(r"\bindemnification\b", re.IGNORECASE),
            ],
        },
        DocumentType.EMPLOYMENT_DOCUMENT: {
            "strong": [
                re.compile(r"\bemployment\s+agreement\b", re.IGNORECASE),
                re.compile(r"\bappointment\s+letter\b", re.IGNORECASE),
                re.compile(r"\boffer\s+of\s+employment\b", re.IGNORECASE),
                re.compile(r"\bcontract\s+of\s+employment\b", re.IGNORECASE),
            ],
            "regular": [
                re.compile(r"\bemployer\b", re.IGNORECASE),
                re.compile(r"\bemployee\b", re.IGNORECASE),
                re.compile(r"\bsalary\b", re.IGNORECASE),
                re.compile(r"\bremuneration\b", re.IGNORECASE),
                re.compile(r"\bprobation\s+period\b", re.IGNORECASE),
                re.compile(r"\bcost\s+to\s+company\b|\bctc\b", re.IGNORECASE),
                re.compile(r"\bnon-compete\b", re.IGNORECASE),
                re.compile(r"\bdesignation\b", re.IGNORECASE),
                re.compile(r"\bduties\s+and\s+responsibilities\b", re.IGNORECASE),
            ],
        },
        DocumentType.LOAN_DOCUMENT: {
            "strong": [
                re.compile(r"\bloan\s+agreement\b", re.IGNORECASE),
                re.compile(r"\bsanction\s+letter\b", re.IGNORECASE),
                re.compile(r"\bloan\s+facility\b", re.IGNORECASE),
                re.compile(r"\bcredit\s+facility\s+agreement\b", re.IGNORECASE),
            ],
            "regular": [
                re.compile(r"\bborrower\b", re.IGNORECASE),
                re.compile(r"\blender\b", re.IGNORECASE),
                re.compile(r"\bprincipal\s+amount\b", re.IGNORECASE),
                re.compile(r"\binterest\s+rate\b", re.IGNORECASE),
                re.compile(r"\brepayment\s+schedule\b", re.IGNORECASE),
                re.compile(r"\bequated\s+monthly\s+installment\b|\bemi\b", re.IGNORECASE),
                re.compile(r"\bhypothecation\b", re.IGNORECASE),
                re.compile(r"\bguarantor\b", re.IGNORECASE),
                re.compile(r"\bcollateral\b", re.IGNORECASE),
            ],
        },
        DocumentType.PROPERTY_DOCUMENT: {
            "strong": [
                re.compile(r"\bsale\s+deed\b", re.IGNORECASE),
                re.compile(r"\blease\s+deed\b", re.IGNORECASE),
                re.compile(r"\bconveyance\s+deed\b", re.IGNORECASE),
                re.compile(r"\brent\s+agreement\b", re.IGNORECASE),
                re.compile(r"\bgift\s+deed\b", re.IGNORECASE),
                re.compile(r"\bschedule\s+of\s+(?:the\s+)?property\b", re.IGNORECASE),
            ],
            "regular": [
                re.compile(r"\bvendor\b", re.IGNORECASE),
                re.compile(r"\bpurchaser\b", re.IGNORECASE),
                re.compile(r"\blessor\b", re.IGNORECASE),
                re.compile(r"\blessee\b", re.IGNORECASE),
                re.compile(r"\blandlord\b", re.IGNORECASE),
                re.compile(r"\btenant\b", re.IGNORECASE),
                re.compile(r"\bpatta\b", re.IGNORECASE),
                re.compile(r"\bkhasra\b|\bkhatauni\b", re.IGNORECASE),
                re.compile(r"\bsub-registrar\b", re.IGNORECASE),
                re.compile(r"\bstamp\s+duty\b", re.IGNORECASE),
                re.compile(r"\bimmovable\s+property\b", re.IGNORECASE),
            ],
        },
        DocumentType.FAMILY_LAW_DOCUMENT: {
            "strong": [
                re.compile(r"\bdivorce\s+petition\b", re.IGNORECASE),
                re.compile(r"\bhindu\s+marriage\s+act\b", re.IGNORECASE),
                re.compile(r"\bspecial\s+marriage\s+act\b", re.IGNORECASE),
                re.compile(r"\brestitution\s+of\s+conjugal\s+rights\b", re.IGNORECASE),
                re.compile(r"\bmutual\s+consent\s+divorce\b", re.IGNORECASE),
                re.compile(r"\bprotection\s+of\s+women\s+from\s+domestic\s+violence\b", re.IGNORECASE),
            ],
            "regular": [
                re.compile(r"\bmarriage\s+solemnized\b", re.IGNORECASE),
                re.compile(r"\bmaintenance\s+petition\b", re.IGNORECASE),
                re.compile(r"\bpermanent\s+alimony\b", re.IGNORECASE),
                re.compile(r"\bchild\s+custody\b", re.IGNORECASE),
                re.compile(r"\bguardianship\b", re.IGNORECASE),
                re.compile(r"\bmatrimonial\s+home\b", re.IGNORECASE),
                re.compile(r"\bfamily\s+court\b", re.IGNORECASE),
                re.compile(r"\binterim\s+maintenance\b", re.IGNORECASE),
            ],
        },
        DocumentType.COURT_DOCUMENT: {
            "strong": [
                re.compile(r"\bin\s+the\s+court\s+of\b", re.IGNORECASE),
                re.compile(r"\bhigh\s+court\s+of\b", re.IGNORECASE),
                re.compile(r"\bsupreme\s+court\s+of\s+india\b", re.IGNORECASE),
                re.compile(r"\bcivil\s+suit\s+no\.?\b", re.IGNORECASE),
                re.compile(r"\bwrit\s+petition\b", re.IGNORECASE),
                re.compile(r"\bcriminal\s+appeal\b", re.IGNORECASE),
            ],
            "regular": [
                re.compile(r"\bplaintiff\b", re.IGNORECASE),
                re.compile(r"\bdefendant\b", re.IGNORECASE),
                re.compile(r"\bpetitioner\b", re.IGNORECASE),
                re.compile(r"\brespondent\b", re.IGNORECASE),
                re.compile(r"\bcivil\s+judge\b", re.IGNORECASE),
                re.compile(r"\bsessions\s+judge\b", re.IGNORECASE),
                re.compile(r"\border\s+sheet\b", re.IGNORECASE),
                re.compile(r"\binterim\s+application\b", re.IGNORECASE),
                re.compile(r"\bdecree\b", re.IGNORECASE),
                re.compile(r"\bjudgement\b", re.IGNORECASE),
            ],
        },
    }

    async def classify(
        self,
        pages: Sequence[Tuple[int, str]],
        filename: str = ""
    ) -> DocumentClassificationResult:
        if not pages or all(not text.strip() for _, text in pages):
            return DocumentClassificationResult(
                document_type=DocumentType.UNKNOWN.value,
                confidence=0.0,
                evidence=[]
            )

        scores: Dict[DocumentType, float] = {doc_type: 0.0 for doc_type in self.CATEGORY_RULES}
        evidence_map: Dict[DocumentType, List[ClassificationEvidence]] = {
            doc_type: [] for doc_type in self.CATEGORY_RULES
        }

        # Check filename as a light heuristic weight
        for doc_type, rules in self.CATEGORY_RULES.items():
            for p in rules["strong"]:
                if p.search(filename):
                    scores[doc_type] += 1.5

        for page_num, text in pages:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            for doc_type, rules in self.CATEGORY_RULES.items():
                # Check strong patterns
                for pattern in rules["strong"]:
                    for line in lines:
                        if pattern.search(line):
                            scores[doc_type] += 3.0
                            if len(evidence_map[doc_type]) < 3:
                                snippet = line if len(line) <= 200 else line[:197] + "..."
                                evidence_map[doc_type].append(
                                    ClassificationEvidence(page=page_num, text=snippet)
                                )
                            break

                # Check regular patterns
                for pattern in rules["regular"]:
                    for line in lines:
                        if pattern.search(line):
                            scores[doc_type] += 1.0
                            if len(evidence_map[doc_type]) < 5:
                                snippet = line if len(line) <= 200 else line[:197] + "..."
                                # Avoid duplicating exact same snippet in evidence
                                if not any(e.text == snippet for e in evidence_map[doc_type]):
                                    evidence_map[doc_type].append(
                                        ClassificationEvidence(page=page_num, text=snippet)
                                    )
                            break

        # Disambiguation heuristics between specific and general categories:
        # e.g., an Employment Agreement, Loan Agreement, or Lease Deed has "Agreement" (Contract) keywords,
        # but the specific subcategory (EMPLOYMENT, LOAN, PROPERTY) takes precedence if strong matches exist.
        for specific in [
            DocumentType.EMPLOYMENT_DOCUMENT,
            DocumentType.LOAN_DOCUMENT,
            DocumentType.PROPERTY_DOCUMENT,
            DocumentType.FAMILY_LAW_DOCUMENT,
        ]:
            if scores[specific] >= 3.0 and scores[specific] >= (scores[DocumentType.CONTRACT] * 0.6):
                scores[specific] += 2.0

        # Sort categories by score descending
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        top_type, top_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0

        # Scoring logic:
        # High confidence (0.90 - 0.95): Score >= 6.0 and clearly leads runner up
        # Medium confidence (0.70 - 0.89): Score >= 3.0
        # Low confidence (< 0.70): Score < 3.0 -> UNKNOWN
        if top_score >= 6.0 and (top_score - second_score >= 2.0 or top_score >= 8.0):
            confidence = min(0.95, 0.90 + (top_score - 6.0) * 0.01)
            selected_type = top_type
        elif top_score >= 3.0:
            confidence = min(0.88, 0.70 + (top_score - 3.0) * 0.04)
            selected_type = top_type
        elif top_score >= 1.5:
            # Low confidence - mark as UNKNOWN rather than guessing per specification
            confidence = min(0.65, top_score / 3.0 * 0.65)
            selected_type = DocumentType.UNKNOWN
        else:
            confidence = 0.10
            selected_type = DocumentType.UNKNOWN

        # Prepare evidence list
        evidence = evidence_map.get(top_type, [])
        if selected_type == DocumentType.UNKNOWN:
            # If unknown, include any weak evidence for transparency or empty
            evidence = evidence[:2] if evidence else []

        return DocumentClassificationResult(
            document_type=selected_type.value,
            confidence=round(confidence, 2),
            evidence=evidence,
        )
