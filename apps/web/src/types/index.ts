export interface ApiError {
  code: string;
  message: string;
  retryable: boolean;
  details?: Record<string, unknown> | null;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  error: ApiError | null;
}

export interface ComponentHealth {
  connected: boolean;
  message: string;
}

export interface HealthData {
  status: string;
  service: string;
  version: string;
  environment: string;
  database?: ComponentHealth | null;
  redis?: ComponentHealth | null;
}

export type DocumentProcessingStatus =
  | "UPLOADED"
  | "VALIDATING"
  | "PROCESSING"
  | "EXTRACTING"
  | "OCR_REQUIRED"
  | "OCR_PROCESSING"
  | "EXTRACTED"
  | "READY"
  | "FAILED"
  | "DELETING"
  | "DELETED";

export interface DocumentUploadData {
  document_id: string;
  status: DocumentProcessingStatus;
  filename: string;
  expires_at: string;
}

export interface DocumentStatusInfo {
  document_id: string;
  status: DocumentProcessingStatus;
  progress: number;
  stage: string;
  error?: string | null;
  retryable: boolean;
}

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

export interface DocumentPageItem {
  page_number: number;
  text: string;
  ocr_used: boolean;
  ocr_confidence?: number | null;
  width?: number | null;
  height?: number | null;
}

export interface DocumentPagesList {
  document_id: string;
  page_count: number;
  pages: DocumentPageItem[];
}
