import { api } from '../client';
import type {
  Product, ProductCreateRequest, ProductPublic, ProductUpdateRequest, Sku, SkuCreateRequest, SkuUpdateRequest,
} from '@/types/domain';
import type { ListResponse } from '@/types/api';

export const productsApi = {
  list: (params: Record<string, unknown>) => api.get<ListResponse<Product>>('/products', { params }),
  create: (body: ProductCreateRequest) => api.post<Product>('/products', body),
  publicList: (params: Record<string, unknown>) =>
    api.get<ListResponse<ProductPublic>>('/products/search', { params }),
  search: (params: Record<string, unknown>) => api.get<ListResponse<ProductPublic>>('/products/search', { params }),
  detail: (id: number) => api.get<Product>(`/products/${id}`),
  update: (id: number, body: ProductUpdateRequest) => api.patch<Product>(`/products/${id}`, body),
  publish: (id: number) => api.post<Product>(`/products/${id}/publish`, {}),
  unpublish: (id: number) => api.post<Product>(`/products/${id}/unpublish`, {}),
  skus: (id: number, params: Record<string, unknown> = {}) => api.get<ListResponse<Sku>>(`/products/${id}/skus`, { params }),
  createSku: (id: number, body: SkuCreateRequest) => api.post<Sku>(`/products/${id}/skus`, body),
  updateSku: (skuId: number, body: SkuUpdateRequest) => api.patch<Sku>(`/skus/${skuId}`, body),
  publicDetail: (id: number) => api.get<ProductPublic>(`/products/${id}/public`, { skipAuthRefresh: true }),
};
