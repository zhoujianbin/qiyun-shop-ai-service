import { api } from '../client';
import type { Refund, RefundAttempt, RefundCreateRequest } from '@/types/domain';
import type { ListResponse } from '@/types/api';

export const refundsApi = {
  list: (params: Record<string, unknown>) => api.get<ListResponse<Refund>>('/refunds', { params }),
  create: (body: RefundCreateRequest) => api.post<Refund>('/refunds', body),
  detail: (id: number) => api.get<Refund>(`/refunds/${id}`),
  execute: (id: number) => api.post<Refund>(`/refunds/${id}/execute`, {}),
  attempts: (id: number, params: Record<string, unknown> = {}) =>
    api.get<ListResponse<RefundAttempt>>(`/refunds/${id}/attempts`, { params }),
};
