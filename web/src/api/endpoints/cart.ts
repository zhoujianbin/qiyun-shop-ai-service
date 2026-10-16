import { api } from '../client';
import type { Cart, CartItemAddRequest, CartItemUpdateRequest } from '@/types/domain';

export const cartApi = {
  get: (params: Record<string, unknown> = {}) => api.get<Cart>('/cart', { params }),
  addItem: (body: CartItemAddRequest) => api.post<Cart>('/cart/items', body),
  updateItem: (id: number, body: CartItemUpdateRequest) => api.patch<Cart>(`/cart/items/${id}`, body),
  removeItem: (id: number) => api.delete<void>(`/cart/items/${id}`),
};
