/** 权限码与角色码常量（与 OpenAPI Role/Permission 枚举一致）。 */

export const PERMISSIONS = [
  'shop:product:read', 'shop:product:write',
  'shop:inventory:read', 'shop:inventory:write',
  'shop:order:read', 'shop:order:write',
  'shop:payment:read', 'shop:fulfillment:write',
  'shop:aftersales:read', 'shop:aftersales:review',
  'shop:invoice:read', 'shop:invoice:write',
  'shop:customer:read', 'shop:customer:write',
  'shop:channel:read', 'shop:channel:write',
  'shop:report:read',
  'shared:staff:read', 'shared:staff:write',
  'shared:role:read', 'shared:role:write',
  'shared:audit:read',
] as const;
export type PermissionCode = (typeof PERMISSIONS)[number];

export const P = {
  productRead: 'shop:product:read',
  productWrite: 'shop:product:write',
  inventoryRead: 'shop:inventory:read',
  inventoryWrite: 'shop:inventory:write',
  orderRead: 'shop:order:read',
  orderWrite: 'shop:order:write',
  paymentRead: 'shop:payment:read',
  fulfillmentWrite: 'shop:fulfillment:write',
  aftersalesRead: 'shop:aftersales:read',
  aftersalesReview: 'shop:aftersales:review',
  invoiceRead: 'shop:invoice:read',
  invoiceWrite: 'shop:invoice:write',
  customerRead: 'shop:customer:read',
  customerWrite: 'shop:customer:write',
  channelRead: 'shop:channel:read',
  channelWrite: 'shop:channel:write',
  reportRead: 'shop:report:read',
  staffRead: 'shared:staff:read',
  staffWrite: 'shared:staff:write',
  roleRead: 'shared:role:read',
  roleWrite: 'shared:role:write',
  auditRead: 'shared:audit:read',
} as const satisfies Record<string, PermissionCode>;

export const ROLE_CODES = [
  'ENTERPRISE_ADMIN', 'ECOM_OPERATOR', 'INVENTORY_KEEPER',
  'AFTER_SALES_SPECIALIST', 'FINANCE_AUDITOR', 'SERVICE_SUPERVISOR',
] as const;
export type RoleCode = (typeof ROLE_CODES)[number];

export const ROLE_LABELS: Record<RoleCode, string> = {
  ENTERPRISE_ADMIN: '企业管理员',
  ECOM_OPERATOR: '电商运营',
  INVENTORY_KEEPER: '库存/仓管',
  AFTER_SALES_SPECIALIST: '售后专员',
  FINANCE_AUDITOR: '财务/只读审计',
  SERVICE_SUPERVISOR: '客服主管',
};
