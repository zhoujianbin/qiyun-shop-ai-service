import { api } from '../client';
import type {
  ChunkPage, ChunkPreviewItem, DocumentPage, GovernanceReport, ImportJob, KnowledgeChunk,
  KnowledgeDocument, KnowledgeOverview, KnowledgeRule, KnowledgeVersion, PublishResult,
  RetrievalResult, ReviewComment, ReviewTask, RuleConflict, RuleImportResult,
} from '@/types/knowledge';

/** 多文件上传：字段名固定 files（后端一次请求多文件）。 */
function asForm(files: File[]): FormData {
  const form = new FormData();
  files.forEach((file) => form.append('files', file));
  return form;
}

const multipart = { headers: { 'Content-Type': 'multipart/form-data' } } as const;

export const knowledgeApi = {
  overview: () => api.get<KnowledgeOverview>('/knowledge/overview'),

  documents: (params: Record<string, unknown>) => api.get<DocumentPage>('/knowledge/documents', { params }),
  document: (documentPk: number | string) => api.get<KnowledgeDocument>(`/knowledge/documents/${documentPk}`),
  versions: (documentPk: number | string) =>
    api.get<KnowledgeVersion[]>(`/knowledge/documents/${documentPk}/versions`),
  chunks: (versionId: number | string, params: Record<string, unknown>) =>
    api.get<ChunkPage>(`/knowledge/versions/${versionId}/chunks`, { params }),

  importFiles: (files: File[]) => api.post<ImportJob>('/knowledge/import/jobs', asForm(files), multipart),
  importJob: (jobId: number | string) => api.get<ImportJob>(`/knowledge/import/jobs/${jobId}`),
  previewChunks: (content_md: string) =>
    api.post<ChunkPreviewItem[]>('/knowledge/preview-chunks', { content_md }),

  submit: (versionId: number | string) => api.post<KnowledgeVersion>(`/knowledge/versions/${versionId}/submit`),
  publish: (versionId: number | string, body: { change_summary: string; effective_from?: string }) =>
    api.post<PublishResult>(`/knowledge/versions/${versionId}/publish`, body),
  rollback: (versionId: number | string) =>
    api.post<KnowledgeVersion>(`/knowledge/versions/${versionId}/rollback`),

  rules: (params: Record<string, unknown> = {}) => api.get<KnowledgeRule[]>('/knowledge/rules', { params }),
  rule: (rulePk: number | string) => api.get<KnowledgeRule>(`/knowledge/rules/${rulePk}`),
  createRule: (body: Record<string, unknown>) => api.post<KnowledgeRule>('/knowledge/rules', body),
  updateRule: (rulePk: number | string, body: Record<string, unknown>) =>
    api.patch<KnowledgeRule>(`/knowledge/rules/${rulePk}`, body),
  importRules: (files: File[]) =>
    api.post<RuleImportResult>('/knowledge/rules/import', asForm(files), multipart),
  checkConflicts: () => api.post<RuleConflict[]>('/knowledge/rules/check-conflicts'),
  conflicts: (params: Record<string, unknown> = {}) =>
    api.get<RuleConflict[]>('/knowledge/rule-conflicts', { params }),
  resolveConflict: (conflictId: number | string) =>
    api.patch<RuleConflict>(`/knowledge/rule-conflicts/${conflictId}`),

  reviewTasks: (params: Record<string, unknown> = {}) =>
    api.get<ReviewTask[]>('/knowledge/review/tasks', { params }),
  reviewTask: (taskId: number | string) => api.get<ReviewTask>(`/knowledge/review/tasks/${taskId}`),
  claimTask: (taskId: number | string) =>
    api.post<ReviewTask>(`/knowledge/review/tasks/${taskId}/claim`),
  decideTask: (taskId: number | string, body: { decision: string; note: string }) =>
    api.post<ReviewTask>(`/knowledge/review/tasks/${taskId}/decide`, body),
  comments: (taskId: number | string) =>
    api.get<ReviewComment[]>(`/knowledge/review/tasks/${taskId}/comments`),
  addComment: (taskId: number | string, body: { anchor: Record<string, unknown>; content: string }) =>
    api.post<ReviewComment>(`/knowledge/review/tasks/${taskId}/comments`, body),

  retrievalTest: (body: {
    query: string;
    top_k: number;
    filters: Record<string, unknown>;
    identity_level: string;
  }) => api.post<RetrievalResult>('/knowledge/retrieval/test', body),
  governanceReport: () => api.get<GovernanceReport>('/knowledge/governance/report'),
};

export type { KnowledgeChunk };
