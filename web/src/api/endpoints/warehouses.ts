import { api } from '../client';
import type { Warehouse, WarehouseCreateRequest } from '@/types/domain';
import type { ListResponse } from '@/types/api';

export const warehousesApi = {
  list: (params: Record<string, unknown> = {}) => api.get<ListResponse<Warehouse>>('/warehouses', { params }),
  create: (body: WarehouseCreateRequest) => api.post<Warehouse>('/warehouses', body),
};
