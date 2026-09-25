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
 * Processing status states for an uploaded legal document.
 */
export enum DocumentProcessingStatus {
  PENDING = "PENDING",
  UPLOADING = "UPLOADING",
  PROCESSING = "PROCESSING",
  OCR_IN_PROGRESS = "OCR_IN_PROGRESS",
  ANALYZING = "ANALYZING",
  INDEXING = "INDEXING",
  COMPLETED = "COMPLETED",
  FAILED = "FAILED",
  EXPIRED = "EXPIRED"
}

/**
 * Document classifications for Indian legal context.
 */
export enum DocumentType {
  LEGAL_NOTICE = "LEGAL_NOTICE",
  EMPLOYMENT_AGREEMENT = "EMPLOYMENT_AGREEMENT",
  RENT_LEASE_AGREEMENT = "RENT_LEASE_AGREEMENT",
  COMMERCIAL_CONTRACT = "COMMERCIAL_CONTRACT",
  COURT_ORDER = "COURT_ORDER",
  WRIT_PETITION = "WRIT_PETITION",
  CONSUMER_COMPLAINT = "CONSUMER_COMPLAINT",
  LOAN_AGREEMENT = "LOAN_AGREEMENT",
  GENERAL_AFFIDAVIT = "GENERAL_AFFIDAVIT",
  OTHER = "OTHER"
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
