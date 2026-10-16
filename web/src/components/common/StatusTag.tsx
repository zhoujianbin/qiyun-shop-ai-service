import Tag from 'antd/es/tag';
import {
  AFTER_SALES_STATUS_COLORS, AFTER_SALES_STATUS_LABELS, AFTER_SALES_TYPE_LABELS,
  FULFILLMENT_STATUS_COLORS, FULFILLMENT_STATUS_LABELS,
  INVOICE_STATUS_COLORS, INVOICE_STATUS_LABELS,
  ORDER_AFTER_SALES_STATUS_LABELS, ORDER_STATUS_COLORS, ORDER_STATUS_LABELS,
  PAYMENT_STATUS_COLORS, PAYMENT_STATUS_LABELS,
  PRODUCT_STATUS_COLORS, PRODUCT_STATUS_LABELS, REFUND_STATUS_COLORS, REFUND_STATUS_LABELS,
  SHIPMENT_STATUS_LABELS, SKU_STATUS_LABELS,
} from '@/constants/statusMaps';

export type StatusKind =
  | 'order' | 'payment' | 'fulfillment' | 'orderAfterSales' | 'afterSales' | 'afterSalesType'
  | 'product' | 'sku' | 'refund' | 'invoice' | 'shipment';

export interface StatusTagProps {
  kind: StatusKind;
  value?: string | null;
  color?: string;
}

function meta(kind: StatusKind, value: string): { label: string; color: string } {
  switch (kind) {
    case 'order':
      return { label: ORDER_STATUS_LABELS[value as keyof typeof ORDER_STATUS_LABELS] ?? value, color: ORDER_STATUS_COLORS[value as keyof typeof ORDER_STATUS_COLORS] ?? 'default' };
    case 'payment':
      return { label: PAYMENT_STATUS_LABELS[value as keyof typeof PAYMENT_STATUS_LABELS] ?? value, color: PAYMENT_STATUS_COLORS[value as keyof typeof PAYMENT_STATUS_COLORS] ?? 'default' };
    case 'fulfillment':
      return { label: FULFILLMENT_STATUS_LABELS[value as keyof typeof FULFILLMENT_STATUS_LABELS] ?? value, color: FULFILLMENT_STATUS_COLORS[value as keyof typeof FULFILLMENT_STATUS_COLORS] ?? 'default' };
    case 'orderAfterSales':
      return { label: ORDER_AFTER_SALES_STATUS_LABELS[value as keyof typeof ORDER_AFTER_SALES_STATUS_LABELS] ?? value, color: 'default' };
    case 'afterSales':
      return { label: AFTER_SALES_STATUS_LABELS[value as keyof typeof AFTER_SALES_STATUS_LABELS] ?? value, color: AFTER_SALES_STATUS_COLORS[value as keyof typeof AFTER_SALES_STATUS_COLORS] ?? 'default' };
    case 'afterSalesType':
      return { label: AFTER_SALES_TYPE_LABELS[value as keyof typeof AFTER_SALES_TYPE_LABELS] ?? value, color: 'blue' };
    case 'product':
      return { label: PRODUCT_STATUS_LABELS[value as keyof typeof PRODUCT_STATUS_LABELS] ?? value, color: PRODUCT_STATUS_COLORS[value as keyof typeof PRODUCT_STATUS_COLORS] ?? 'default' };
    case 'sku':
      return { label: SKU_STATUS_LABELS[value as keyof typeof SKU_STATUS_LABELS] ?? value, color: 'default' };
    case 'refund':
      return { label: REFUND_STATUS_LABELS[value as keyof typeof REFUND_STATUS_LABELS] ?? value, color: REFUND_STATUS_COLORS[value as keyof typeof REFUND_STATUS_COLORS] ?? 'default' };
    case 'invoice':
      return { label: INVOICE_STATUS_LABELS[value as keyof typeof INVOICE_STATUS_LABELS] ?? value, color: INVOICE_STATUS_COLORS[value as keyof typeof INVOICE_STATUS_COLORS] ?? 'default' };
    case 'shipment':
      return { label: SHIPMENT_STATUS_LABELS[value as keyof typeof SHIPMENT_STATUS_LABELS] ?? value, color: 'default' };
    default:
      return { label: value, color: 'default' };
  }
}

/** 状态三重编码：颜色 + 文字（图标由 antd Tag 语义补充）。 */
export function StatusTag({ kind, value, color }: StatusTagProps) {
  if (!value) return <span>-</span>;
  const m = meta(kind, value);
  return <Tag color={color ?? m.color}>{m.label}</Tag>;
}
