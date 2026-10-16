import { api } from '../client';
import type { MockPaymentSucceedRequest, Payment, PaymentCreateRequest } from '@/types/domain';
import type { ListResponse } from '@/types/api';

export const paymentsApi = {
  create: (body: PaymentCreateRequest) => api.post<Payment>('/payments', body),
  list: (params: Record<string, unknown> = {}) => api.get<ListResponse<Payment>>('/payments', { params }),
  detail: (id: number) => api.get<Payment>(`/payments/${id}`),
  mockSucceed: (id: number, body: MockPaymentSucceedRequest = {}) => api.post<Payment>(`/payments/${id}/mock-succeed`, body),
};
