import { api } from '../client';
import type { AfterSalesReport, DashboardReport, InventoryReport, SalesDailyReport } from '@/types/domain';
import type { ListResponse } from '@/types/api';

export const reportsApi = {
  dashboard: (params: Record<string, unknown>) => api.get<DashboardReport>('/reports/dashboard', { params }),
  salesDaily: (params: Record<string, unknown>) =>
    api.get<ListResponse<SalesDailyReport>>('/reports/sales/daily', { params }),
  inventory: (params: Record<string, unknown> = {}) => api.get<InventoryReport>('/reports/inventory', { params }),
  afterSales: (params: Record<string, unknown>) => api.get<AfterSalesReport>('/reports/after-sales', { params }),
};
