/** 二期知识库类型（与 app/schemas/knowledge.py 对齐）。 */

export interface PageMeta {
  page: number;
  page_size: number;
  total: number;
}

export interface KnowledgeDocument {
  id: number;
  document_id: string;
  title: string;
  category: string;
  owner?: string | null;
  status: string;
  current_version?: number | null;
  identity_level: string;
  effective_date?: string | null;
  product_scope?: string | null;
  channel_scope?: string[];
  metadata?: Record<string, unknown>;
  updated_at?: string | null;
  chunk_count?: number | null;
  versions?: KnowledgeVersion[];
  active_version?: KnowledgeVersion | null;
}

export interface DocumentPage {
  page: number;
  page_size: number;
  total: number;
  items: KnowledgeDocument[];
  meta: PageMeta;
}

export interface KnowledgeVersion {
  id: number;
  document_pk: number;
  version: number;
  status: string;
  checksum: string;
  change_summary?: string | null;
  source_kind?: string;
  effective_from?: string | null;
  published_at?: string | null;
  created_by?: number | null;
  created_at?: string | null;
  content_md?: string;
}

export interface KnowledgeChunk {
  id: number;
  ord: number;
  title_path: string;
  content: string;
  char_count: number;
  token_count?: number | null;
  embedding_status: string;
  identity_level: string;
  line_start?: number | null;
  line_end?: number | null;
}

export interface ChunkPage {
  page: number;
  page_size: number;
  total: number;
  items: KnowledgeChunk[];
}

export interface PublishInfo {
  change_summary: string;
  affected_scope: { product_scope?: string | null; channel_scope?: string[] };
  citation_count: number;
  rollback_target?: number | null;
}

export interface PublishResult extends KnowledgeVersion {
  publish_info: PublishInfo;
  reasons: string[];
}

export interface ImportErrorItem {
  file: string;
  reason: string;
  line?: number | null;
}

export interface ImportJob {
  id: number;
  source_type: string;
  status: string;
  total: number;
  succeeded: number;
  failed: number;
  skipped: number;
  errors: ImportErrorItem[];
  created_at?: string | null;
}

export interface ChunkPreviewItem {
  ord: number;
  title_path: string;
  content: string;
  char_count: number;
  line_start: number;
  line_end: number;
}

export interface KnowledgeRule {
  id: number;
  rule_id: string;
  source_kind: string;
  condition: Record<string, unknown>;
  action: Record<string, unknown>;
  forbid: unknown[];
  priority: number;
  status: string;
  conflict_group?: string | null;
  source_file?: string | null;
}

export interface RuleConflict {
  id: number;
  rule_a_id: number;
  rule_b_id: number;
  conflict_type: string;
  severity: string;
  status: string;
  detail: Record<string, unknown>;
  resolved_at?: string | null;
}

export interface RuleImportResult {
  imported: number;
  updated: number;
  total: number;
  by_source_kind: Record<string, number>;
  open_conflicts: number;
}

export interface ReviewTask {
  id: number;
  document_version_id: number;
  assignee_id?: number | null;
  status: string;
  decision?: string | null;
  note?: string | null;
  self_review: boolean;
  created_at?: string | null;
  version?: { id: number; version: number; status: string; change_summary?: string | null; created_by?: number | null };
  document?: { id: number; document_id: string; title: string; category: string } | null;
  conflicts?: RuleConflict[];
}

export interface ReviewComment {
  id: number;
  version_id: number;
  task_id?: number | null;
  author_id?: number | null;
  anchor: Record<string, unknown>;
  content: string;
  resolved: boolean;
  created_at?: string | null;
}

export interface RetrievalHit {
  source_type: string;
  chunk_id: number;
  document_id: string;
  document_pk: number;
  version: number;
  chunk_ord: number;
  title_path: string;
  line_start?: number | null;
  line_end?: number | null;
  snippet: string;
}

export interface RetrievalDebug {
  vector_score: Record<string, number>;
  text_score: Record<string, number>;
  fused_score: Record<string, number>;
  latency_ms: number;
  candidates?: number;
}

export interface RetrievalResult {
  hits: RetrievalHit[];
  debug: RetrievalDebug;
}

export interface GovernanceItem {
  type: string;
  document_id?: string | null;
  title: string;
  detail: string;
  filter: Record<string, unknown>;
}

export interface GovernanceReport {
  duplicate: GovernanceItem[];
  expired: GovernanceItem[];
  orphan: GovernanceItem[];
  conflict: GovernanceItem[];
  inconsistent: GovernanceItem[];
  counts: Record<string, number>;
}

export interface KnowledgeOverview {
  documents: number;
  chunks: number;
  pending_review: number;
  expired: number;
  conflicts: number;
  governance: Record<string, number>;
}
/** 四期：本体实体/关系/图。 */
export interface OntologyEntity {
  id: number;
  code: string;
  kind: string;
  name: string;
  summary?: string | null;
  status: 'DRAFT' | 'APPROVED' | 'DEPRECATED';
  source?: string | null;
  attrs?: Record<string, unknown>;
}

export interface OntologyRelation {
  id: number;
  predicate: string;
  src_entity_id: number;
  dst_entity_id: number;
  src_code?: string | null;
  dst_code?: string | null;
  status: string;
}

export interface OntologyGraphNode {
  entity: OntologyEntity;
  depth: number;
  via: string;
}

export interface OntologyGraph {
  root: OntologyEntity;
  nodes: OntologyGraphNode[];
  edge_count: number;
  depth: number;
}
