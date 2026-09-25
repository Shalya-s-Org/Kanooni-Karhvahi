/**
 * Kanooni Karhvahi - Shared Domain Contracts & Constants
 */

export const APP_NAME = "Kanooni Karhvahi";
export const APP_TAGLINE = "A Multilingual Legal-Document Companion for India";

/**
 * Standard Legal Disclaimer required on every user interface view.
 */
export const LEGAL_DISCLAIMER =
  "Kanooni Karhvahi is an AI-powered legal document comprehension tool designed for informational purposes only. It is not an attorney, law firm, or substitute for legal counsel. It does not provide legal advice, representation, or outcome predictions.";

/**
 * Processing state machine for an uploaded legal document (Phase 2 specification).
 */
export enum DocumentProcessingStatus {
  UPLOADED = "UPLOADED",
  VALIDATING = "VALIDATING",
  PROCESSING = "PROCESSING",
  EXTRACTING = "EXTRACTING",
  OCR_REQUIRED = "OCR_REQUIRED",
  OCR_PROCESSING = "OCR_PROCESSING",
  EXTRACTED = "EXTRACTED",
  CLASSIFYING = "CLASSIFYING",
  EXTRACTING_ENTITIES = "EXTRACTING_ENTITIES",
  SEGMENTING_CLAUSES = "SEGMENTING_CLAUSES",
  READY = "READY",
  FAILED = "FAILED",
  DELETING = "DELETING",
  DELETED = "DELETED"
}

/**
 * Controlled document classifications for Indian legal context (Phase 3).
 */
export enum DocumentType {
  FIR = "FIR",
  GOVERNMENT_NOTICE = "GOVERNMENT_NOTICE",
  LEGAL_NOTICE = "LEGAL_NOTICE",
  CONTRACT = "CONTRACT",
  PROPERTY_DOCUMENT = "PROPERTY_DOCUMENT",
  EMPLOYMENT_DOCUMENT = "EMPLOYMENT_DOCUMENT",
  LOAN_DOCUMENT = "LOAN_DOCUMENT",
  FAMILY_LAW_DOCUMENT = "FAMILY_LAW_DOCUMENT",
  COURT_DOCUMENT = "COURT_DOCUMENT",
  OTHER = "OTHER",
  UNKNOWN = "UNKNOWN"
}


/**
 * Supported Indian regional languages for translation & explanation.
 */
export enum SupportedLanguage {
  EN = "en", // English
  HI = "hi", // Hindi
  BN = "bn", // Bengali
  TE = "te", // Telugu
  MR = "mr", // Marathi
  TA = "ta", // Tamil
  GU = "gu", // Gujarati
  KN = "kn", // Kannada
  ML = "ml", // Malayalam
  PA = "pa"  // Punjabi
}

/**
 * Standard API error structure.
 */
export interface ApiError {
  code: string;
  message: string;
  retryable: boolean;
  details?: Record<string, unknown> | null;
}

/**
 * Standard API response envelope.
 */
export interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  error: ApiError | null;
}

/**
 * Document metadata transfer object.
 */
export interface DocumentMetadata {
  id: string;
  filename: string;
  mime_type: string;
  size: number;
  page_count: number;
  status: DocumentProcessingStatus;
  created_at: string;
  expires_at: string;
}

/**
 * Document page extracted text object.
 */
export interface DocumentPageItem {
  page_number: number;
  text: string;
  ocr_used: boolean;
  ocr_confidence: number | null;
  width: number | null;
  height: number | null;
}

/**
 * Document status polling response.
 */
export interface DocumentStatusInfo {
  document_id: string;
  status: DocumentProcessingStatus;
  progress: number;
  stage: string;
  error: string | null;
  retryable: boolean;
}

/**
  * Document classification evidence.
  */
export interface ClassificationEvidence {
  page: number;
  text: string;
}

/**
  * Document classification result.
  */
export interface DocumentClassificationInfo {
  document_type: DocumentType | string;
  confidence: number;
  evidence: ClassificationEvidence[];
}

/**
  * Structured extracted entity with source traceability.
  */
export interface DocumentEntityItem {
  id: string;
  document_id: string;
  page_id?: string | null;
  page_number: number;
  entity_type: string;
  value: string;
  normalized_value?: string | null;
  entity_metadata?: Record<string, unknown> | null;
  source_text: string;
  start_offset?: number | null;
  end_offset?: number | null;
  confidence: number;
  created_at: string;
}

/**
  * Segmented document clause/section.
  */
export interface DocumentClauseItem {
  id: string;
  document_id: string;
  page_id?: string | null;
  clause_number?: string | null;
  title?: string | null;
  original_text: string;
  page_start: number;
  page_end: number;
  confidence: number;
  created_at: string;
}

