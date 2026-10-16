import type { ProductStatus, SkuStatus, ProductType, ChangeType, InvoiceStatus, InvoiceType } from '@/types/status';

export { PRODUCT_LINES } from '@/types/status';

export const PRODUCT_STATUS_LABELS: Record<ProductStatus, string> = {
  DRAFT: '草稿', ON_SALE: '在售', OFF_SHELF: '已下架', ARCHIVED: '已归档',
};
export const PRODUCT_STATUS_COLORS: Record<ProductStatus, string> = {
  DRAFT: 'default', ON_SALE: 'success', OFF_SHELF: 'warning', ARCHIVED: 'default',
};
export const PRODUCT_STATUS_OPTIONS = (Object.keys(PRODUCT_STATUS_LABELS) as ProductStatus[]).map((value) => ({
  value, label: PRODUCT_STATUS_LABELS[value],
}));

export const SKU_STATUS_LABELS: Record<SkuStatus, string> = {
  ON_SALE: '在售', OFF_SHELF: '已下架', ARCHIVED: '已归档',
};

export const PRODUCT_TYPE_LABELS: Record<ProductType, string> = {
  SMART_LOCK: '智能门锁', CAMERA: '家用摄像头', CLEANING_ROBOT: '清洁机器人', SMART_LIGHT: '智能灯具',
  HOME_GATEWAY: '家庭网关', ACCESSORY: '配件', CONSUMABLE: '耗材',
  CLOUD_SERVICE: '云服务', INSTALL_SERVICE: '安装服务',
};
export const PRODUCT_TYPE_OPTIONS = (Object.keys(PRODUCT_TYPE_LABELS) as ProductType[]).map((value) => ({
  value, label: PRODUCT_TYPE_LABELS[value],
}));

export const CHANGE_TYPE_LABELS: Record<ChangeType, string> = {
  PURCHASE_IN: '采购入库', SALE_OUT: '销售出库', RESERVE: '锁定', RELEASE: '释放锁定',
  RETURN_IN: '退货入库', ADJUST: '盘点修正', DAMAGE: '报损', TRANSFER_IN: '调拨入', TRANSFER_OUT: '调拨出',
};

export const ADJUST_TYPE_OPTIONS = [
  { value: 'PURCHASE_IN', label: '采购入库（+）' },
  { value: 'RETURN_IN', label: '退货入库（+）' },
  { value: 'TRANSFER_IN', label: '调拨入库（+）' },
  { value: 'TRANSFER_OUT', label: '调拨出库（-）' },
  { value: 'ADJUST', label: '盘点修正（±）' },
  { value: 'DAMAGE', label: '报损（-）' },
];

export const STOCK_ADJUST_REASONS = [
  { value: 'PURCHASE_ARRIVAL', label: '采购到货' },
  { value: 'INVENTORY_CHECK', label: '库存盘点' },
  { value: 'DAMAGED', label: '商品破损' },
  { value: 'RETURN', label: '客户退货' },
  { value: 'TRANSFER', label: '仓间调拨' },
  { value: 'OTHER', label: '其他' },
];

export const INVOICE_STATUS_LABELS: Record<InvoiceStatus, string> = {
  DRAFT: '草稿', PENDING: '待开票', ISSUED: '已开票', VOID: '已作废',
};
export const INVOICE_STATUS_COLORS: Record<InvoiceStatus, string> = {
  DRAFT: 'default', PENDING: 'warning', ISSUED: 'success', VOID: 'default',
};
export const INVOICE_TYPE_LABELS: Record<InvoiceType, string> = {
  VAT_NORMAL: '增值税普通发票', VAT_SPECIAL: '增值税专用发票', ELECTRONIC: '电子普通发票',
};
export const INVOICE_TYPE_OPTIONS = (Object.keys(INVOICE_TYPE_LABELS) as InvoiceType[]).map((value) => ({
  value, label: INVOICE_TYPE_LABELS[value],
}));
export const INVOICE_STATUS_OPTIONS = (Object.keys(INVOICE_STATUS_LABELS) as InvoiceStatus[]).map((value) => ({
  value, label: INVOICE_STATUS_LABELS[value],
}));
