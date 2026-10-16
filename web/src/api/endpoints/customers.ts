import { api } from '../client';
import type {
  Customer, CustomerAddress, CustomerAddressRequest, CustomerUpdateRequest, Order,
} from '@/types/domain';
import type { ListResponse } from '@/types/api';

export const customersApi = {
  list: (params: Record<string, unknown>) => api.get<ListResponse<Customer>>('/customers', { params }),
  detail: (id: number) => api.get<Customer>(`/customers/${id}`),
  update: (id: number, body: CustomerUpdateRequest) => api.patch<Customer>(`/customers/${id}`, body),
  addresses: (id: number) => api.get<CustomerAddress[]>(`/customers/${id}/addresses`),
  myAddresses: () => api.get<CustomerAddress[]>('/customers/me/addresses'),
  createMyAddress: (body: CustomerAddressRequest) =>
    api.post<CustomerAddress>('/customers/me/addresses', body),
  updateMyAddress: (addressId: number, body: CustomerAddressRequest) =>
    api.patch<CustomerAddress>(`/customers/me/addresses/{addressId}`, body),
  deleteMyAddress: (addressId: number) => api.delete<void>(`/customers/me/addresses/{addressId}`),
  createAddress: (id: number, body: CustomerAddressRequest) => api.post<CustomerAddress>(`/customers/${id}/addresses`, body),
  updateAddress: (addressId: number, body: CustomerAddressRequest) =>
    api.patch<CustomerAddress>(`/customers/addresses/${addressId}`, body),
  deleteAddress: (addressId: number) => api.delete<void>(`/customers/addresses/${addressId}`),
  orders: (id: number, params: Record<string, unknown> = {}) =>
    api.get<ListResponse<Order>>(`/customers/${id}/orders`, { params }),
};
