/** 契约枚举的唯一来源（与 OpenAPI 3.1 对齐）。禁止在页面散落字符串字面量。 */

export const ORDER_STATUSES = [
  'CREATED', 'PENDING_PAYMENT', 'PAID', 'FULFILLING', 'SHIPPED', 'COMPLETED', 'CANCELLED', 'CLOSED',
] as const;
export type OrderStatus = (typeof ORDER_STATUSES)[number];

export const PAYMENT_STATUSES = ['UNPAID', 'PARTIAL', 'PAID', 'REFUNDING', 'PARTIAL_REFUNDED', 'REFUNDED'] as const;
export type PaymentStatus = (typeof PAYMENT_STATUSES)[number];

export const FULFILLMENT_STATUSES = ['UNSHIPPED', 'PARTIAL_SHIPPED', 'SHIPPED', 'DELIVERED'] as const;
export type FulfillmentStatus = (typeof FULFILLMENT_STATUSES)[number];

export const ORDER_AFTER_SALES_STATUSES = ['NONE', 'APPLYING', 'PROCESSING', 'COMPLETED', 'REJECTED'] as const;
export type OrderAfterSalesStatus = (typeof ORDER_AFTER_SALES_STATUSES)[number];

export const AFTER_SALES_STATUSES = [
  'SUBMITTED', 'REVIEWING', 'APPROVED', 'REJECTED', 'WAITING_RETURN',
  'RETURN_SHIPPED', 'RECEIVED', 'REFUNDING', 'COMPLETED', 'CANCELLED',
] as const;
export type AfterSalesStatus = (typeof AFTER_SALES_STATUSES)[number];

export const AFTER_SALES_TYPES = ['REFUND_ONLY', 'RETURN_REFUND', 'EXCHANGE', 'REPAIR'] as const;
export type AfterSalesType = (typeof AFTER_SALES_TYPES)[number];

export const PRODUCT_STATUSES = ['DRAFT', 'ON_SALE', 'OFF_SHELF', 'ARCHIVED'] as const;
export type ProductStatus = (typeof PRODUCT_STATUSES)[number];

export const SKU_STATUSES = ['ON_SALE', 'OFF_SHELF', 'ARCHIVED'] as const;
export type SkuStatus = (typeof SKU_STATUSES)[number];

export const PRODUCT_TYPES = [
  'SMART_LOCK', 'CAMERA', 'CLEANING_ROBOT', 'SMART_LIGHT', 'HOME_GATEWAY',
  'ACCESSORY', 'CONSUMABLE', 'CLOUD_SERVICE', 'INSTALL_SERVICE',
] as const;
export type ProductType = (typeof PRODUCT_TYPES)[number];

export const PRODUCT_LINES = [
  '智能门锁', '家用摄像头', '清洁机器人', '智能灯具', '家庭网关', '配件耗材', '云服务', '安装维修',
] as const;
export type ProductLine = (typeof PRODUCT_LINES)[number];

export const REFUND_STATUSES = ['PENDING', 'PROCESSING', 'SUCCESS', 'FAILED', 'CANCELLED'] as const;
export type RefundStatus = (typeof REFUND_STATUSES)[number];

export const INVOICE_STATUSES = ['DRAFT', 'PENDING', 'ISSUED', 'VOID'] as const;
export type InvoiceStatus = (typeof INVOICE_STATUSES)[number];

export const INVOICE_TYPES = ['VAT_NORMAL', 'VAT_SPECIAL', 'ELECTRONIC'] as const;
export type InvoiceType = (typeof INVOICE_TYPES)[number];

export const PAYMENT_METHODS = ['MOCK', 'WECHAT_PAY', 'ALIPAY', 'UNIONPAY', 'BALANCE'] as const;
export type PaymentMethod = (typeof PAYMENT_METHODS)[number];

export const PAYMENT_STATUSES_PAY = ['PENDING', 'SUCCESS', 'FAILED', 'CLOSED'] as const;
export type PayStatus = (typeof PAYMENT_STATUSES_PAY)[number];

export const SHIPMENT_STATUSES = ['PENDING', 'PICKED_UP', 'IN_TRANSIT', 'DELIVERED', 'EXCEPTION', 'RETURNED'] as const;
export type ShipmentStatus = (typeof SHIPMENT_STATUSES)[number];

export const CHANNEL_TYPES = ['OFFICIAL_MALL', 'ECOM_FLAGSHIP', 'AUTHORIZED_RETAIL'] as const;
export type ChannelType = (typeof CHANNEL_TYPES)[number];

export const CHANGE_TYPES = ['PURCHASE_IN', 'SALE_OUT', 'RESERVE', 'RELEASE', 'RETURN_IN', 'ADJUST', 'DAMAGE', 'TRANSFER_IN', 'TRANSFER_OUT'] as const;
export type ChangeType = (typeof CHANGE_TYPES)[number];

export const ADJUST_TYPES = ['ADJUST', 'DAMAGE', 'PURCHASE_IN', 'RETURN_IN', 'TRANSFER_IN', 'TRANSFER_OUT'] as const;
export type AdjustType = (typeof ADJUST_TYPES)[number];

export const STAFF_STATUSES = ['ACTIVE', 'DISABLED', 'LOCKED', 'PENDING'] as const;
export type StaffStatus = (typeof STAFF_STATUSES)[number];

export const WAREHOUSE_TYPES = ['SELF', 'THIRD_PARTY', 'VIRTUAL'] as const;
export type WarehouseType = (typeof WAREHOUSE_TYPES)[number];

export const PARTIES = ['STAFF', 'CUSTOMER', 'GUEST'] as const;
export type Party = (typeof PARTIES)[number];

export const ORDER_SOURCES = ['OFFICIAL_MALL', 'ECOMMERCE', 'RETAIL', 'MANUAL'] as const;
export type OrderSource = (typeof ORDER_SOURCES)[number];
