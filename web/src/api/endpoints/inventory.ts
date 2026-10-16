import { api } from '../client';
import type { InventoryItem, InventoryLedgerEntry, StockAdjustRequest } from '@/types/domain';
import type { ListResponse } from '@/types/api';

export const inventoryApi = {
  list: (params: Record<string, unknown>) => api.get<ListResponse<InventoryItem>>('/inventory', { params }),
  adjust: (body: StockAdjustRequest) => api.post<InventoryLedgerEntry>('/inventory/adjust', body),
  ledger: (params: Record<string, unknown>) => api.get<ListResponse<InventoryLedgerEntry>>('/inventory/ledger', { params }),
  alerts: (params: Record<string, unknown> = {}) => api.get<ListResponse<InventoryItem>>('/inventory/alerts', { params }),
};
