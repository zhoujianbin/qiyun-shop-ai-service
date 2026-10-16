import { api } from '../client';
import type {
  CreateOrderRequest, Order, OrderAddressUpdateRequest, OrderCancelRequest, OrderRemarkUpdateRequest,
  OrderTimelineEntry, ShipRequest, Shipment,
} from '@/types/domain';
import type { ListResponse } from '@/types/api';

export const ordersApi = {
  create: (body: CreateOrderRequest) => api.post<Order>('/orders', body),
  list: (params: Record<string, unknown>) => api.get<ListResponse<Order>>('/orders', { params }),
  detail: (id: number) => api.get<Order>(`/orders/${id}`),
  cancel: (id: number, body: OrderCancelRequest) => api.post<Order>(`/orders/${id}/cancel`, body),
  confirmReceipt: (id: number) => api.post<Order>(`/orders/${id}/confirm-receipt`, {}),
  updateAddress: (id: number, body: OrderAddressUpdateRequest) => api.patch<Order>(`/orders/${id}/address`, body),
  updateRemark: (id: number, body: OrderRemarkUpdateRequest) => api.patch<Order>(`/orders/${id}/remark`, body),
  timeline: (id: number, params: Record<string, unknown> = {}) =>
    api.get<ListResponse<OrderTimelineEntry>>(`/orders/${id}/timeline`, { params }),
  ship: (id: number, body: ShipRequest) => api.post<Shipment>(`/orders/${id}/ship`, body),
};
