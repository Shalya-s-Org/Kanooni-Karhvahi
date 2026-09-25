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

export type _DocumentProcessingStatusLegacy = never; // replaced — see bottom of file

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

export interface ClassificationEvidence {
  page: number;
  text: string;
}

export interface DocumentClassificationInfo {
  document_type: string;
  confidence: number;
  evidence: ClassificationEvidence[];
}

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

export interface DocumentEntityList {
  document_id: string;
  total_count: number;
  entities: DocumentEntityItem[];
}

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

export interface DocumentClauseList {
  document_id: string;
  total_count: number;
  clauses: DocumentClauseItem[];
}

// ─── Phase 4: Semantic Retrieval ────────────────────────────────────────────

export interface RetrievalResultItem {
  chunk_id: string;
  text: string;
  score: number;
  page_number: number;
  page_id: string | null;
  clause_id: string | null;
  clause_number: string | null;
  document_id: string;
  retrieval_method: "semantic" | "lexical" | "hybrid";
  source_type: string;
}

export interface RetrievalResponseData {
  document_id: string;
  query: string;
  results: RetrievalResultItem[];
  total_results: number;
  retrieval_method: string;
}

/** Extend DocumentProcessingStatus with Phase 4 states */
export type DocumentProcessingStatus =
  | "UPLOADED"
  | "VALIDATING"
  | "PROCESSING"
  | "EXTRACTING"
  | "OCR_REQUIRED"
  | "OCR_PROCESSING"
  | "EXTRACTED"
  | "CLASSIFYING"
  | "EXTRACTING_ENTITIES"
  | "SEGMENTING_CLAUSES"
  | "CHUNKING_DOCUMENT"
  | "GENERATING_EMBEDDINGS"
  | "READY"
  | "READY_WITHOUT_EMBEDDINGS"
  | "FAILED"
  | "DELETING"
  | "DELETED";

