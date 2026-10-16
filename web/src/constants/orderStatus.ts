import type { OrderStatus } from '@/types/status';

export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  CREATED: '已创建',
  PENDING_PAYMENT: '待付款',
  PAID: '待发货',
  FULFILLING: '备货中',
  SHIPPED: '已发货',
  COMPLETED: '已完成',
  CANCELLED: '已取消',
  CLOSED: '已关闭',
};

export const ORDER_STATUS_COLORS: Record<OrderStatus, string> = {
  CREATED: 'default', PENDING_PAYMENT: 'warning', PAID: 'processing', FULFILLING: 'processing',
  SHIPPED: 'cyan', COMPLETED: 'success', CANCELLED: 'default', CLOSED: 'default',
};

export const ORDER_STATUS_OPTIONS = (Object.keys(ORDER_STATUS_LABELS) as OrderStatus[]).map((value) => ({
  value, label: ORDER_STATUS_LABELS[value],
}));

/** 取消订单原因枚举（前端字典 + 其他） */
export const CANCEL_REASONS = [
  { value: 'CUSTOMER_REQUEST', label: '客户主动取消' },
  { value: 'OUT_OF_STOCK', label: '库存不足' },
  { value: 'PRICE_ERROR', label: '价格错误' },
  { value: 'ADDRESS_INVALID', label: '地址无法配送' },
  { value: 'OTHER', label: '其他' },
];
