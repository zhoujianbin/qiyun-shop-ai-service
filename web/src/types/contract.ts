/**
 * 契约生成类型入口（由 `npm run gen:api` 从 contracts/openapi.yaml 生成，文件只读）。
 * 领域语义别名见 types/domain.ts；此处保留契约原样访问能力，用于校验字段与枚举。
 */
import type { components, operations, paths } from '@/api/generated/schema';

export type Schemas = components['schemas'];
export type Operations = operations;
export type ApiPaths = paths;

export type ContractCurrentUser = Schemas['CurrentUser'];
export type ContractOrder = Schemas['Order'];
export type ContractProduct = Schemas['Product'];
export type ContractAfterSalesApplication = Schemas['AfterSalesApplication'];
export type ContractRefund = Schemas['Refund'];
export type ContractInvoice = Schemas['Invoice'];
export type ContractApiError = Schemas['ApiError'];
export type ContractDashboardReport = Schemas['DashboardReport'];
