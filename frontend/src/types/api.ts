// Mirrors backend Pydantic DTOs (CLAUDE.md §6.18). Keep in sync with app/schemas.

export interface UserPublic {
  id: string;
  username: string;
  roles: string[];
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: UserPublic;
}

export interface RefreshResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserMe {
  id: string;
  username: string;
  email: string | null;
  roles: string[];
  is_active: boolean;
}

export interface Citation {
  marker: number;
  document_id: string;
  chunk_id: string;
  page_number: number | null;
  char_start: number;
  char_end: number;
  snippet: string;
}

export interface RetrievedChunk {
  chunk_id: string;
  document_id: string;
  score: number;
  page_number: number | null;
  content_preview: string;
}

export interface DocGrade {
  chunk_id: string;
  relevant: boolean;
  score: number;
}

export interface QueryResponse {
  answer: string;
  insufficient_evidence: boolean;
  faithful: boolean;
  faithfulness_score: number;
  citations: Citation[];
  retrieved_chunks: RetrievedChunk[];
  doc_grades: DocGrade[];
  correction_applied: boolean;
  latency_ms: number;
  request_id: string;
}

export interface DocumentSummary {
  id: string;
  filename: string;
  classification: string;
  allowed_roles: string[];
  chunk_count: number;
  status: string;
  page_number?: number | null;
  created_at: string;
}

export interface DocumentListResponse {
  items: DocumentSummary[];
  total: number;
  page: number;
  size: number;
}

export interface AuditEntry {
  id: number;
  ts: string;
  actor_id: string | null;
  actor_roles: string[];
  action: string;
  resource_type: string;
  resource_id: string | null;
  outcome: string;
  ip_address: string | null;
  request_id: string;
  details: Record<string, unknown>;
  prev_hash: string;
  entry_hash: string;
}

export interface AuditListResponse {
  items: AuditEntry[];
  total: number;
  page: number;
  size: number;
}

export interface ChainReport {
  ok: boolean;
  total: number;
  first_broken_id: number | null;
  broken_field: string | null;
}

export interface EvalRunSummary {
  id: string;
  suite: string;
  dataset: string;
  passed: boolean;
  faithfulness_avg: number | null;
  hallucination_rate: number | null;
  created_at: string;
}

export interface EvalRunListResponse {
  items: EvalRunSummary[];
  total: number;
}

export interface ApiErrorBody {
  error: { code: string; message: string; request_id: string };
}
