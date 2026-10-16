import type { QueryValue } from '@/utils/queryString';

type Params = Record<string, QueryValue>;

/** queryKey 工厂：第一段资源域，第二段 list/detail，第三段对象参数。 */
export const queryKeys = {
  me: () => ['me'] as const,

  products: {
    all: () => ['products'] as const,
    list: (params: Params) => ['products', 'list', params] as const,
    detail: (id: number | string) => ['products', 'detail', id] as const,
    publicDetail: (id: number | string) => ['products', 'public', id] as const,
    search: (params: Params) => ['products', 'search', params] as const,
  },
  skus: {
    all: () => ['skus'] as const,
    list: (params: Params) => ['skus', 'list', params] as const,
  },
  catalog: {
    categories: (params: Params = {}) => ['catalog', 'categories', params] as const,
    brands: (params: Params = {}) => ['catalog', 'brands', params] as const,
  },
  inventory: {
    all: () => ['inventory'] as const,
    list: (params: Params) => ['inventory', 'list', params] as const,
    ledger: (params: Params) => ['inventory', 'ledger', params] as const,
    alerts: (params: Params) => ['inventory', 'alerts', params] as const,
  },
  warehouses: {
    all: () => ['warehouses'] as const,
    list: (params: Params = {}) => ['warehouses', 'list', params] as const,
  },
  customers: {
    all: () => ['customers'] as const,
    list: (params: Params) => ['customers', 'list', params] as const,
    detail: (id: number | string) => ['customers', 'detail', id] as const,
    addresses: (id: number | string) => ['customers', 'addresses', id] as const,
    orders: (id: number | string, params: Params) => ['customers', 'orders', id, params] as const,
  },
  cart: {
    detail: (params: Params = {}) => ['cart', 'detail', params] as const,
  },
  orders: {
    all: () => ['orders'] as const,
    list: (params: Params) => ['orders', 'list', params] as const,
    detail: (id: number | string) => ['orders', 'detail', id] as const,
    timeline: (id: number | string) => ['orders', 'timeline', id] as const,
  },
  payments: {
    all: () => ['payments'] as const,
    list: (params: Params) => ['payments', 'list', params] as const,
    detail: (id: number | string) => ['payments', 'detail', id] as const,
  },
  shipments: {
    all: () => ['shipments'] as const,
    list: (params: Params) => ['shipments', 'list', params] as const,
    detail: (id: number | string) => ['shipments', 'detail', id] as const,
  },
  carriers: {
    list: (params: Params = {}) => ['carriers', 'list', params] as const,
  },
  afterSales: {
    all: () => ['afterSales'] as const,
    list: (params: Params) => ['afterSales', 'list', params] as const,
    detail: (id: number | string) => ['afterSales', 'detail', id] as const,
  },
  refunds: {
    all: () => ['refunds'] as const,
    list: (params: Params) => ['refunds', 'list', params] as const,
    detail: (id: number | string) => ['refunds', 'detail', id] as const,
    attempts: (id: number | string) => ['refunds', 'attempts', id] as const,
  },
  invoices: {
    all: () => ['invoices'] as const,
    list: (params: Params) => ['invoices', 'list', params] as const,
    detail: (id: number | string) => ['invoices', 'detail', id] as const,
  },
  staff: {
    all: () => ['staff'] as const,
    list: (params: Params) => ['staff', 'list', params] as const,
    detail: (id: number | string) => ['staff', 'detail', id] as const,
    roles: (id: number | string) => ['staff', 'roles', id] as const,
    channelScopes: (id: number | string) => ['staff', 'channelScopes', id] as const,
  },
  roles: {
    all: () => ['roles'] as const,
    list: (params: Params = {}) => ['roles', 'list', params] as const,
  },
  permissions: {
    list: () => ['permissions', 'list'] as const,
  },
  channels: {
    all: () => ['channels'] as const,
    list: (params: Params) => ['channels', 'list', params] as const,
  },
  audit: {
    all: () => ['audit'] as const,
    list: (params: Params) => ['audit', 'list', params] as const,
  },
  reports: {
    dashboard: (params: Params) => ['reports', 'dashboard', params] as const,
    salesDaily: (params: Params) => ['reports', 'salesDaily', params] as const,
    inventory: (params: Params) => ['reports', 'inventory', params] as const,
    afterSales: (params: Params) => ['reports', 'afterSales', params] as const,
  },
};
