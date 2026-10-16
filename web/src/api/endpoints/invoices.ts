import { api } from '../client';
import type { Invoice, InvoiceCreateRequest, InvoiceIssueRequest, InvoiceVoidRequest } from '@/types/domain';
import type { ListResponse } from '@/types/api';

export const invoicesApi = {
  list: (params: Record<string, unknown>) => api.get<ListResponse<Invoice>>('/invoices', { params }),
  create: (body: InvoiceCreateRequest) => api.post<Invoice>('/invoices', body),
  detail: (id: number) => api.get<Invoice>(`/invoices/${id}`),
  issue: (id: number, body: InvoiceIssueRequest) => api.post<Invoice>(`/invoices/${id}/issue`, body),
  void: (id: number, body: InvoiceVoidRequest) => api.post<Invoice>(`/invoices/${id}/void`, body),
};
