from enum import Enum


class DocumentType(str, Enum):
    """
    Controlled extensible document classification categories for Indian legal documents.
    """
    FIR = "FIR"
    GOVERNMENT_NOTICE = "GOVERNMENT_NOTICE"
    LEGAL_NOTICE = "LEGAL_NOTICE"
    CONTRACT = "CONTRACT"
    PROPERTY_DOCUMENT = "PROPERTY_DOCUMENT"
    EMPLOYMENT_DOCUMENT = "EMPLOYMENT_DOCUMENT"
    LOAN_DOCUMENT = "LOAN_DOCUMENT"
    FAMILY_LAW_DOCUMENT = "FAMILY_LAW_DOCUMENT"
    COURT_DOCUMENT = "COURT_DOCUMENT"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"
