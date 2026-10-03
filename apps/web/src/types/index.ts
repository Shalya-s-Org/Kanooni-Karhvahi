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

// ─── Phase 5: AI Comprehension & Analysis ───────────────────────────────────

export type CheckSignalSeverity = "INFO" | "ATTENTION" | "HIGH_ATTENTION";

export interface CheckSignal {
  category: string;
  message: string;
  severity: CheckSignalSeverity;
  evidence_refs: string[];
  explanation?: string;
}

export interface KeyPoint {
  text: string;
  evidence_refs: string[];
}

export interface ImportantTerm {
  term: string;
  explanation: string;
}

export type AnalysisLifecycleStatus =
  | "PENDING"
  | "GENERATING"
  | "COMPLETED"
  | "VALIDATION_FAILED"
  | "FAILED"
  | "PROVIDER_UNAVAILABLE";

export interface DocumentSummaryData {
  analysis_id: string;
  document_id: string;
  status: AnalysisLifecycleStatus | string;
  summary?: string | null;
  purpose?: string | null;
  document_type?: string | null;
  key_points: KeyPoint[];
  important_dates: string[];
  important_amounts: string[];
  important_parties: string[];
  obligations: string[];
  check_signals: CheckSignal[];
  uncertainty_notes: string[];
  evidence_refs: string[];
  legal_citations?: LegalCitation[] | null;
  external_legal_context?: string[] | null;
  provider?: string | null;
  model?: string | null;
  prompt_version?: string | null;
  error_message?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ClauseExplanationData {
  analysis_id: string;
  document_id: string;
  clause_id: string;
  status: AnalysisLifecycleStatus | string;
  original_text?: string | null;
  clause_number?: string | null;
  clause_title?: string | null;
  page_start?: number | null;
  plain_meaning?: string | null;
  why_it_matters?: string | null;
  important_terms: ImportantTerm[];
  obligations: string[];
  dates: string[];
  amounts: string[];
  check_signals: CheckSignal[];
  uncertainty_notes: string[];
  evidence_refs: string[];
  legal_citations?: LegalCitation[] | null;
  external_legal_context?: string[] | null;
  provider?: string | null;
  model?: string | null;
  prompt_version?: string | null;
  error_message?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

// ---------------------------------------------------------------------------
// Phase 6: Verified Legal Source Types
// ---------------------------------------------------------------------------

export interface LegalCitation {
  citation_id: string;
  source_name: string;
  authority: string;
  source_type: string;
  section?: string | null;
  subsection?: string | null;
  version: string;
  effective_date?: string | null;
  official_url: string;
  retrieved_at: string;
}

export interface LegalSourceVersion {
  id: string;
  legal_source_id: string;
  version_identifier: string;
  effective_from?: string | null;
  effective_to?: string | null;
  publication_date?: string | null;
  retrieved_at: string;
  content_hash: string;
  source_url: string;
  status: string;
  created_at: string;
}

export interface LegalSource {
  id: string;
  name: string;
  source_type: string;
  authority: string;
  official_url: string;
  description?: string | null;
  jurisdiction: string;
  language: string;
  active: boolean;
  trust_level: string;
  created_at: string;
  updated_at: string;
  versions?: LegalSourceVersion[];
}

export interface LegalRetrievalResult {
  chunk_id: string;
  legal_source_id: string;
  legal_source_name: string;
  authority: string;
  source_type: string;
  official_url: string;
  version_id: string;
  version_identifier: string;
  effective_from?: string | null;
  effective_to?: string | null;
  section?: string | null;
  subsection?: string | null;
  page_or_reference?: string | null;
  source_text: string;
  score: number;
  retrieval_method: string;
  citation: LegalCitation;
}

export interface LegalSourceRetrieveResponse {
  query: string;
  results: LegalRetrievalResult[];
  citations: LegalCitation[];
}


// ---------------------------------------------------------------------------
// Phase 7: Multilingual Translation Types
// ---------------------------------------------------------------------------

export interface SupportedLanguageItem {
  code: string;
  name: string;
}

export interface SupportedLanguagesResponse {
  languages: SupportedLanguageItem[];
  preserve_terms_note: string;
}

export interface TranslationData {
  translation_id: string;
  document_id?: string | null;
  source_language: string;
  target_language: string;
  target_language_name: string;
  content_type: string;
  clause_id?: string | null;
  original_text: string;
  translated_text: string;
  preserved_terms: string[];
  provider: string;
  model: string;
  created_at: string;
  status: "COMPLETED" | "FAILED";
  error_message?: string | null;
}
