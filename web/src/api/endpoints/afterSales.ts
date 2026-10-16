import { api } from '../client';
import type {
  AfterSalesApplication, AfterSalesCancelRequest, AfterSalesCompleteRequest, AfterSalesCreateRequest,
  AfterSalesMessage, AfterSalesMessageCreateRequest, AfterSalesReceiveRequest, ReviewRequest, ReturnShipmentRequest,
} from '@/types/domain';
import type { ListResponse } from '@/types/api';

export const afterSalesApi = {
  create: (body: AfterSalesCreateRequest) => api.post<AfterSalesApplication>('/after-sales/applications', body),
  list: (params: Record<string, unknown>) =>
    api.get<ListResponse<AfterSalesApplication>>('/after-sales/applications', { params }),
  detail: (id: number) => api.get<AfterSalesApplication>(`/after-sales/applications/${id}`),
  review: (id: number, body: ReviewRequest) =>
    api.post<AfterSalesApplication>(`/after-sales/applications/${id}/review`, body),
  returnShipment: (id: number, body: ReturnShipmentRequest) =>
    api.post<AfterSalesApplication>(`/after-sales/applications/${id}/return-shipment`, body),
  receive: (id: number, body: AfterSalesReceiveRequest) =>
    api.post<AfterSalesApplication>(`/after-sales/applications/${id}/receive`, body),
  complete: (id: number, body: AfterSalesCompleteRequest) =>
    api.post<AfterSalesApplication>(`/after-sales/applications/${id}/complete`, body),
  cancel: (id: number, body: AfterSalesCancelRequest) =>
    api.post<AfterSalesApplication>(`/after-sales/applications/${id}/cancel`, body),
  addMessage: (id: number, body: AfterSalesMessageCreateRequest) =>
    api.post<AfterSalesMessage>(`/after-sales/applications/${id}/messages`, body),
};
