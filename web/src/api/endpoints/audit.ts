import { api } from '../client';
import type { AuditLog } from '@/types/domain';
import type { ListResponse } from '@/types/api';

export const auditApi = {
  list: (params: Record<string, unknown>) => api.get<ListResponse<AuditLog>>('/audit-logs', { params }),
};
