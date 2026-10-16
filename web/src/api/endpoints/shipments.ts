import { api } from '../client';
import type { Carrier, Shipment, TrackingEvent, TrackingEventCreateRequest } from '@/types/domain';
import type { ListResponse } from '@/types/api';

export const shipmentsApi = {
  carriers: (params: Record<string, unknown> = {}) => api.get<ListResponse<Carrier>>('/carriers', { params }),
  list: (params: Record<string, unknown> = {}) => api.get<ListResponse<Shipment>>('/shipments', { params }),
  detail: (id: number) => api.get<Shipment>(`/shipments/${id}`),
  addTrackingEvent: (id: number, body: TrackingEventCreateRequest) =>
    api.post<TrackingEvent>(`/shipments/${id}/tracking-events`, body),
};
