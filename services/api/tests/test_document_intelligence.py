import uuid
import pytest
from httpx import AsyncClient
import fitz  # PyMuPDF
from app.services.document_service import document_service
from app.classification.enums import DocumentType
from app.classification.rule_based_classifier import RuleBasedDocumentClassifier
from app.extraction.date_extractor import DateExtractor
from app.extraction.amount_extractor import AmountExtractor
from app.extraction.parties_extractor import PartiesExtractor
from app.extraction.authorities_extractor import AuthoritiesExtractor
from app.extraction.reference_extractor import ReferenceExtractor
from app.extraction.legal_sections_extractor import LegalSectionsExtractor
from app.extraction.contact_extractor import ContactExtractor
from app.extraction.orchestrator import EntityExtractionService
from app.clauses.segmenter import ClauseSegmentationService


def create_sample_pdf(num_pages: int = 1, text: str = "") -> bytes:
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 72), f"Page {i + 1}:\n{text}", fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ---------------------------------------------------------------------------
# FIXTURES FOR LEGAL DOCUMENT CATEGORIES
# ---------------------------------------------------------------------------

LEGAL_NOTICE_TEXT = """
LEGAL NOTICE
UNDER INSTRUCTIONS FROM MY CLIENT
Advocate R. K. Sharma, High Court of Delhi
Chamber 402, Lawyers Chambers, New Delhi
Email: advocate.sharma@example.com | Phone: +91 9876543210

Ref No: LN/2026/089
Date: 15 October 2026

To,
Noticee: M/s Alpha Trading Pvt. Ltd.
Through its Director Mr. Vikram Verma

SUBJECT: STATUTORY DEMAND NOTICE UNDER SECTION 138 OF NEGOTIABLE INSTRUMENTS ACT, 1881

Sir,
Under instructions from my client, Shri Ramesh Gupta, residing at Hauz Khas, New Delhi, I hereby serve upon you this Legal Notice:
1. That you issued Cheque No. 445210 for an amount of Rs. 2,50,000/- drawn on State Bank of India towards discharge of legal debt.
2. That the said cheque was returned unpaid by the bank with remarks "Funds Insufficient".
3. I hereby call upon you to pay the said sum of Rs. 2,50,000 on or before 30 October 2026 or reply within 15 days from receipt of this notice, failing which my client shall initiate criminal prosecution under Section 138 of Negotiable Instruments Act without prejudice to other civil remedies.
"""


CONTRACT_TEXT = """
COMMERCIAL SERVICES AGREEMENT
This Agreement is entered into on 01 November 2026 (the "Effective Date") by and between:
ABC Technologies Ltd. (hereinafter referred to as the 'Client')
AND
XYZ Solutions Pvt. Ltd. (hereinafter referred to as the 'Service Provider')

WHEREAS the Client desires to obtain software maintenance services, and whereas the Service Provider agrees to provide such services.
NOW THEREFORE, in consideration of mutual covenants, the parties agree as follows:

1. DEFINITIONS
"Confidential Information" shall mean all proprietary business information disclosed by either party.

2. SCOPE OF SERVICES
The Service Provider shall render technical services as detailed in Schedule A.

3. CONSIDERATION AND PAYMENT TERMS
The Client shall pay a consideration of ₹5,00,000 per quarter. Any delayed payment shall attract a penalty of ₹10,000 per month.

4. TERM AND TERMINATION
This Agreement shall remain valid till 31 October 2027 unless terminated earlier. Either party may terminate with 30 days notice.

5. GOVERNING LAW AND JURISDICTION
This Agreement shall be governed by the laws of India and subject to the exclusive jurisdiction of courts in Mumbai.
IN WITNESS WHEREOF the parties hereto have executed this Agreement.
"""

FIR_TEXT = """
FIRST INFORMATION REPORT
(Under Section 154 CrPC)
Police Station: Hauz Khas
District: South Delhi
FIR No. 245/2026
Date & Time of FIR: 12/08/2026 14:30 hrs

1. Complainant: Smt. Sunita Devi, w/o Late Mohan Lal
2. Accused: Rajesh Kumar, s/o Om Prakash
3. Sections of Law: Section 420, Section 467, Section 468, and Section 471 of Indian Penal Code (IPC)
4. Place of Occurrence: Near Green Park Metro Station, Hauz Khas
5. Brief Facts of the Case:
The complainant reported that the accused fraudulently induced her to transfer ₹3,00,000 on the pretext of government job allocation. Cognizable offence under sections of law registered.
"""

GOVERNMENT_NOTICE_TEXT = """
GOVERNMENT OF INDIA
MINISTRY OF ENVIRONMENT, FOREST AND CLIMATE CHANGE
CENTRAL POLLUTION CONTROL BOARD
Public Notice & Show Cause Notice
Notice Ref: CPCB/COMPLIANCE/2026/778
Date of Issue: 20 September 2026

To:
Noticee: Horizon Chemicals Ltd.
Industrial Area, Phase II, Ghaziabad

Subject: Compliance Notice and Order under Section 5 of Environment (Protection) Act, 1986

WHEREAS inspection conducted by the competent authority revealed non-compliance with effluent standards.
NOW THEREFORE, in exercise of powers under Section 5 of the Act:
1. You are directed to show cause within 15 days of this notice why environmental compensation should not be levied.
2. You are liable to pay environmental compensation of ₹10,00,000 as penalty for repeated violations.
Hearing on: 10 November 2026 before the Chairman, Central Pollution Control Board.
"""

EMPLOYMENT_DOCUMENT_TEXT = """
APPOINTMENT LETTER AND EMPLOYMENT AGREEMENT
Date: 01 June 2026

To:
Employee: Mr. Amit Sharma
Designation: Senior Legal Associate

Dear Amit,
We are pleased to offer you employment with Global Law Partners (the "Employer") on the following terms and conditions:
1. Remuneration: Your annual Cost to Company (CTC) salary will be ₹12,00,000 payable monthly.
2. Probation Period: You will be on probation for 6 months commencing from 15 June 2026.
3. Notice Period: Following confirmation, either party may terminate employment by giving 60 days written notice.
4. Non-Compete: During employment and for 12 months thereafter, you shall not solicit clients of the Employer.
"""

LOAN_DOCUMENT_TEXT = """
LOAN FACILITY AGREEMENT
Sanction Letter No: LOAN/SBN/2026/1102
Dated: 05 July 2026

Between:
Lender: State Bank of India, Commercial Branch, Bengaluru
AND
Borrower: Srikanth Rao, residing at Indiranagar, Bengaluru

Principal Amount: ₹50,00,000 (Rupees Fifty Lakhs only)
Interest Rate: 8.75% per annum
Repayment Schedule: The borrower agrees to repay through Equated Monthly Installment (EMI) of ₹65,000 payable on or before 10th of every calendar month for 120 months.
Hypothecation and Collateral: Secured against mortgage of residential property at Indiranagar.
"""

PROPERTY_DOCUMENT_TEXT = """
DEED OF ABSOLUTE SALE (SALE DEED)
This Sale Deed executed on 14 February 2026 before the Sub-Registrar Office, Pune.
Between:
Vendor: Shri Narayan Patil, s/o Tukaram Patil
AND
Purchaser: Smt. Priya Deshmukh, w/o Anil Deshmukh

Schedule of the Property:
All that piece and parcel of immovable property bearing Khasra No. 142, Survey No. 88, situated at Hadapsar, Pune.
Total Consideration: The total purchase price and consideration is ₹45,00,000 paid via Demand Draft.
The Vendor has paid all required Stamp Duty and registration charges.
"""

COURT_DOCUMENT_TEXT = """
IN THE COURT OF DISTRICT & SESSIONS JUDGE, PATIALA HOUSE COURTS, NEW DELHI
Civil Suit No. 102/2026

Ramesh Chandra Gupta ... Plaintiff
VERSUS
M/s Modern Buildcon Pvt. Ltd. ... Defendant

ORDER UNDER ORDER XXXIX RULE 1 AND 2 OF CODE OF CIVIL PROCEDURE (CPC)
Date of Order: 18 May 2026
The Plaintiff filed interim application seeking temporary injunction restraining Defendant from creating third-party rights.
Next date of hearing fixed for 22 July 2026 before this Court.
"""

UNRELATED_TEXT = """
Cooking Recipe: How to bake chocolate chip cookies.
Preheat oven to 350 degrees. Take 2 cups of all-purpose flour, 1 teaspoon of baking soda, and 1/2 cup of softened butter.
Mix together and bake for 10 to 12 minutes until golden brown.
Random serial codes: 994829104, 381920194, 8821.
"""


# ---------------------------------------------------------------------------
# UNIT TESTS: CLASSIFICATION
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classification_legal_notice():
    classifier = RuleBasedDocumentClassifier()
    res = await classifier.classify([(1, LEGAL_NOTICE_TEXT)], filename="notice.pdf")
    assert res.document_type == DocumentType.LEGAL_NOTICE.value
    assert res.confidence >= 0.85
    assert len(res.evidence) >= 1
    assert any("notice" in e.text.lower() or "section" in e.text.lower() for e in res.evidence)



@pytest.mark.asyncio
async def test_classification_contract():
    classifier = RuleBasedDocumentClassifier()
    res = await classifier.classify([(1, CONTRACT_TEXT)], filename="services_agreement.pdf")
    assert res.document_type == DocumentType.CONTRACT.value
    assert res.confidence >= 0.85
    assert len(res.evidence) >= 1


@pytest.mark.asyncio
async def test_classification_fir():
    classifier = RuleBasedDocumentClassifier()
    res = await classifier.classify([(1, FIR_TEXT)], filename="fir_report.pdf")
    assert res.document_type == DocumentType.FIR.value
    assert res.confidence >= 0.85
    assert len(res.evidence) >= 1


@pytest.mark.asyncio
async def test_classification_government_notice():
    classifier = RuleBasedDocumentClassifier()
    res = await classifier.classify([(1, GOVERNMENT_NOTICE_TEXT)], filename="govt_notice.pdf")
    assert res.document_type == DocumentType.GOVERNMENT_NOTICE.value
    assert res.confidence >= 0.80


@pytest.mark.asyncio
async def test_classification_employment():
    classifier = RuleBasedDocumentClassifier()
    res = await classifier.classify([(1, EMPLOYMENT_DOCUMENT_TEXT)], filename="offer_letter.pdf")
    assert res.document_type == DocumentType.EMPLOYMENT_DOCUMENT.value
    assert res.confidence >= 0.85


@pytest.mark.asyncio
async def test_classification_loan():
    classifier = RuleBasedDocumentClassifier()
    res = await classifier.classify([(1, LOAN_DOCUMENT_TEXT)], filename="loan_sanction.pdf")
    assert res.document_type == DocumentType.LOAN_DOCUMENT.value
    assert res.confidence >= 0.85


@pytest.mark.asyncio
async def test_classification_property():
    classifier = RuleBasedDocumentClassifier()
    res = await classifier.classify([(1, PROPERTY_DOCUMENT_TEXT)], filename="sale_deed.pdf")
    assert res.document_type == DocumentType.PROPERTY_DOCUMENT.value
    assert res.confidence >= 0.85


@pytest.mark.asyncio
async def test_classification_court_document():
    classifier = RuleBasedDocumentClassifier()
    res = await classifier.classify([(1, COURT_DOCUMENT_TEXT)], filename="court_order.pdf")
    assert res.document_type == DocumentType.COURT_DOCUMENT.value
    assert res.confidence >= 0.85


@pytest.mark.asyncio
async def test_classification_unrelated_text_unknown():
    classifier = RuleBasedDocumentClassifier()
    res = await classifier.classify([(1, UNRELATED_TEXT)], filename="recipe.txt")
    assert res.document_type == DocumentType.UNKNOWN.value
    assert res.confidence < 0.70


# ---------------------------------------------------------------------------
# UNIT TESTS: ENTITY EXTRACTION
# ---------------------------------------------------------------------------

def test_date_and_deadline_extractor():
    extractor = DateExtractor()
    sample = (
        "Dated this 15 October 2026. You are required to pay on or before 30 October 2026, "
        "or reply within 15 days from receipt. The next date of hearing is 10/11/2026."
    )
    entities = extractor.extract(sample, page_number=1)
    values = [e.value for e in entities]
    types = [e.entity_type for e in entities]

    assert any("15 October 2026" in v for v in values)
    assert any("30 October 2026" in v for v in values)
    assert any("within 15 days" in v for v in values)
    assert any("10/11/2026" in v for v in values)

    # Check semantic differentiation
    assert "DEADLINE" in types
    assert "DATE" in types

    # Check ISO normalization
    oct_15 = next(e for e in entities if "15 October 2026" in e.value)
    assert oct_15.normalized_value == "2026-10-15"


def test_date_extractor_negative_cases():
    extractor = DateExtractor()
    # Malformed dates or non-dates
    sample = "Batch code 99/99/9999 and random numbers 12345/67890 should not be dates."
    entities = extractor.extract(sample, page_number=1)
    assert len(entities) == 0


def test_amount_extractor():
    extractor = AmountExtractor()
    sample = (
        "Client paid a fee of ₹2,50,000/- with an advance of Rs. 50,000. "
        "Failure incurs a penalty of ₹10,000. Total budget is 5 Lakhs."
    )
    entities = extractor.extract(sample, page_number=1)
    assert len(entities) >= 3

    # Check numeric normalization
    vals = [e.normalized_value for e in entities]
    assert "250000" in vals
    assert "50000" in vals
    assert "10000" in vals
    assert "500000" in vals

    # Check penalty amount type detection
    penalty_ent = next(e for e in entities if "10,000" in e.value)
    assert penalty_ent.metadata.get("amount_type") == "PENALTY"

    # Check currency INR
    assert all(e.metadata.get("currency") == "INR" for e in entities)


def test_amount_extractor_negative_cases():
    extractor = AmountExtractor()
    sample = "In section 420 of code 1881, the number 50000 appears without currency sign."
    entities = extractor.extract(sample, page_number=1)
    assert len(entities) == 0


def test_parties_extractor():
    extractor = PartiesExtractor()
    sample = (
        "Complainant: Shri Ramesh Gupta\n"
        "Accused: Vikram Verma\n"
        "Between ABC Technologies Ltd. (hereinafter referred to as the 'Employer') "
        "and Amit Sharma (hereinafter called 'Employee')"
    )
    entities = extractor.extract(sample, page_number=1)
    assert len(entities) >= 3

    roles = [e.metadata.get("role") for e in entities]
    assert "COMPLAINANT" in roles
    assert "ACCUSED" in roles
    assert "EMPLOYER" in roles or "EMPLOYEE" in roles


def test_authorities_extractor():
    extractor = AuthoritiesExtractor()
    sample = (
        "Registered at Police Station Hauz Khas. "
        "Matter filed in the High Court of Delhi. "
        "Order issued by Ministry of Environment, Forest and Climate Change. "
        "Loan disbursed by State Bank of India."
    )
    entities = extractor.extract(sample, page_number=1)
    vals = [e.value for e in entities]
    assert any("Police Station Hauz Khas" in v for v in vals)
    assert any("High Court of Delhi" in v for v in vals)
    assert any("State Bank of India" in v for v in vals)


def test_reference_extractor():
    extractor = ReferenceExtractor()
    sample = (
        "FIR No. 245/2026 was filed. "
        "Civil Suit No. 102/2026 pending. "
        "Ref No: LN/2026/089 sent. "
        "Random number 9849204 without prefix."
    )
    entities = extractor.extract(sample, page_number=1)
    vals = [e.normalized_value for e in entities]
    assert "245/2026" in vals
    assert "102/2026" in vals
    assert "LN/2026/089" in vals
    # Standalone 9849204 should NOT be extracted
    assert "9849204" not in vals


def test_legal_sections_extractor():
    extractor = LegalSectionsExtractor()
    sample = (
        "Notice under Section 138 of Negotiable Instruments Act, 1881. "
        "Charge under Section 420 and Section 302 IPC, also u/s 467 IPC. "
        "Petition under Article 226 of the Constitution of India. "
        "Order under Order XXXIX Rule 1."
    )
    entities = extractor.extract(sample, page_number=1)
    assert len(entities) >= 4
    vals = [e.value for e in entities]
    assert any("138" in v for v in vals)
    assert any("420" in v for v in vals)
    assert any("Article 226" in v for v in vals)


def test_contact_extractor():
    extractor = ContactExtractor()
    sample = "Please write to advocate.sharma@example.com or call +91 9876543210."
    entities = extractor.extract(sample, page_number=1)
    assert len(entities) == 2
    types = [e.entity_type for e in entities]
    assert "EMAIL" in types
    assert "PHONE_NUMBER" in types


# ---------------------------------------------------------------------------
# UNIT TESTS: CLAUSE SEGMENTATION
# ---------------------------------------------------------------------------

def test_clause_segmentation_service():
    segmenter = ClauseSegmentationService()
    clauses = segmenter.segment_text([(1, CONTRACT_TEXT, None)])
    assert len(clauses) >= 4

    titles = [c.title for c in clauses if c.title]
    numbers = [c.clause_number for c in clauses if c.clause_number]

    assert any("DEFINITIONS" in t.upper() for t in titles)
    assert any("SCOPE" in t.upper() for t in titles)
    assert any("GOVERNING LAW" in t.upper() for t in titles)
    assert any("1" in n for n in numbers)
    assert all(c.confidence >= 0.80 for c in clauses)


# ---------------------------------------------------------------------------
# INTEGRATION TESTS: PIPELINE & API ENDPOINTS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_end_to_end_intelligence_pipeline_and_api(async_client: AsyncClient, test_db_session):
    """
    Upload Legal Notice PDF -> run pipeline through CLASSIFYING, EXTRACTING_ENTITIES, SEGMENTING_CLAUSES -> READY.
    Verify:
      - GET /classification returns LEGAL_NOTICE with confidence and evidence.
      - GET /entities returns structured entities with type filtering.
      - GET /clauses returns clauses.
      - GET /clauses/{clause_id} returns clause details.
    """
    pdf_bytes = create_sample_pdf(num_pages=1, text=LEGAL_NOTICE_TEXT)
    files = {"file": ("demand_notice.pdf", pdf_bytes, "application/pdf")}

    # 1. Upload
    up_res = await async_client.post("/api/v1/documents/upload", files=files)
    assert up_res.status_code == 201
    doc_id = uuid.UUID(up_res.json()["data"]["document_id"])

    # 2. Run pipeline directly
    doc = await document_service.process_document_pipeline(doc_id, test_db_session)
    assert doc.status == "READY"

    # 3. GET /classification
    cls_res = await async_client.get(f"/api/v1/documents/{doc_id}/classification")
    assert cls_res.status_code == 200
    cls_data = cls_res.json()
    assert cls_data["success"] is True
    assert cls_data["data"]["document_type"] == "LEGAL_NOTICE"
    assert cls_data["data"]["confidence"] >= 0.85
    assert len(cls_data["data"]["evidence"]) >= 1

    # 4. GET /entities (all)
    ent_res = await async_client.get(f"/api/v1/documents/{doc_id}/entities")
    assert ent_res.status_code == 200
    ent_data = ent_res.json()
    assert ent_data["success"] is True
    assert ent_data["data"]["total_count"] > 0
    all_types = {e["entity_type"] for e in ent_data["data"]["entities"]}
    assert "AMOUNT" in all_types
    assert "DATE" in all_types or "DEADLINE" in all_types

    # 5. GET /entities?type=AMOUNT filter
    amt_res = await async_client.get(f"/api/v1/documents/{doc_id}/entities?type=AMOUNT")
    assert amt_res.status_code == 200
    amts = amt_res.json()["data"]["entities"]
    assert len(amts) >= 1
    assert all(a["entity_type"] == "AMOUNT" for a in amts)
    assert any("2,50,000" in a["value"] for a in amts)

    # 6. GET /clauses
    clause_res = await async_client.get(f"/api/v1/documents/{doc_id}/clauses")
    assert clause_res.status_code == 200
    clause_data = clause_res.json()
    assert clause_data["success"] is True
    assert clause_data["data"]["total_count"] > 0
    first_clause_id = clause_data["data"]["clauses"][0]["id"]

    # 7. GET /clauses/{clause_id}
    single_res = await async_client.get(f"/api/v1/documents/{doc_id}/clauses/{first_clause_id}")
    assert single_res.status_code == 200
    single_data = single_res.json()
    assert single_data["success"] is True
    assert single_data["data"]["id"] == first_clause_id
    assert len(single_data["data"]["original_text"]) > 0


@pytest.mark.asyncio
async def test_pasted_text_intelligence(async_client: AsyncClient):
    """
    Intake pasted legal notice text -> verify intelligence records are generated and READY.
    """
    payload = {
        "text": FIR_TEXT,
        "filename": "fir_input.txt"
    }
    response = await async_client.post("/api/v1/documents/text", json=payload)
    assert response.status_code == 201
    doc_id = response.json()["data"]["document_id"]

    # Check classification
    cls_res = await async_client.get(f"/api/v1/documents/{doc_id}/classification")
    assert cls_res.status_code == 200
    cls_data = cls_res.json()["data"]
    assert cls_data["document_type"] == "FIR"

    # Check entities
    ent_res = await async_client.get(f"/api/v1/documents/{doc_id}/entities")
    assert ent_res.status_code == 200
    ents = ent_res.json()["data"]["entities"]
    assert len(ents) >= 2
    types = [e["entity_type"] for e in ents]
    assert "REFERENCE_NUMBER" in types
    assert "AUTHORITY" in types
