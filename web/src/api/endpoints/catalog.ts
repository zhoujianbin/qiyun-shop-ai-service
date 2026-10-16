import { api } from '../client';
import type {
  Brand, BrandCreateRequest, Category, CategoryCreateRequest, CategoryUpdateRequest,
} from '@/types/domain';
import type { ListResponse } from '@/types/api';

export const catalogApi = {
  categories: (params: Record<string, unknown> = {}) => api.get<Category[]>('/categories', { params }),
  createCategory: (body: CategoryCreateRequest) => api.post<Category>('/categories', body),
  updateCategory: (body: CategoryUpdateRequest) => api.patch<Category>('/categories/' + body.id, body),
  brands: (params: Record<string, unknown> = {}) => api.get<ListResponse<Brand>>('/brands', { params }),
  createBrand: (body: BrandCreateRequest) => api.post<Brand>('/brands', body),
};
