import type { AfterSalesStatus, AfterSalesType, OrderAfterSalesStatus, RefundStatus } from '@/types/status';

export const AFTER_SALES_STATUS_LABELS: Record<AfterSalesStatus, string> = {
  SUBMITTED: '已提交', REVIEWING: '审核中', APPROVED: '已通过', REJECTED: '已驳回',
  WAITING_RETURN: '待寄回', RETURN_SHIPPED: '已寄回', RECEIVED: '已收货',
  REFUNDING: '退款中', COMPLETED: '已完成', CANCELLED: '已取消',
};
export const AFTER_SALES_STATUS_COLORS: Record<AfterSalesStatus, string> = {
  SUBMITTED: 'processing', REVIEWING: 'processing', APPROVED: 'success', REJECTED: 'error',
  WAITING_RETURN: 'warning', RETURN_SHIPPED: 'cyan', RECEIVED: 'cyan',
  REFUNDING: 'processing', COMPLETED: 'success', CANCELLED: 'default',
};
export const AFTER_SALES_STATUS_OPTIONS = (Object.keys(AFTER_SALES_STATUS_LABELS) as AfterSalesStatus[]).map((value) => ({
  value, label: AFTER_SALES_STATUS_LABELS[value],
}));

export const AFTER_SALES_TYPE_LABELS: Record<AfterSalesType, string> = {
  REFUND_ONLY: '仅退款', RETURN_REFUND: '退货退款', EXCHANGE: '换货', REPAIR: '维修',
};
export const AFTER_SALES_TYPE_OPTIONS = (Object.keys(AFTER_SALES_TYPE_LABELS) as AfterSalesType[]).map((value) => ({
  value, label: AFTER_SALES_TYPE_LABELS[value],
}));

export const ORDER_AFTER_SALES_STATUS_LABELS: Record<OrderAfterSalesStatus, string> = {
  NONE: '无售后', APPLYING: '申请中', PROCESSING: '处理中', COMPLETED: '已完成', REJECTED: '已驳回',
};
export const ORDER_AFTER_SALES_STATUS_OPTIONS = (Object.keys(ORDER_AFTER_SALES_STATUS_LABELS) as OrderAfterSalesStatus[]).map((value) => ({
  value, label: ORDER_AFTER_SALES_STATUS_LABELS[value],
}));

export const REFUND_STATUS_LABELS: Record<RefundStatus, string> = {
  PENDING: '待处理', PROCESSING: '退款中', SUCCESS: '退款成功', FAILED: '退款失败', CANCELLED: '已取消',
};
export const REFUND_STATUS_COLORS: Record<RefundStatus, string> = {
  PENDING: 'warning', PROCESSING: 'processing', SUCCESS: 'success', FAILED: 'error', CANCELLED: 'default',
};
export const REFUND_STATUS_OPTIONS = (Object.keys(REFUND_STATUS_LABELS) as RefundStatus[]).map((value) => ({
  value, label: REFUND_STATUS_LABELS[value],
}));

export const AFTER_SALES_REASON_OPTIONS = [
  { value: 'QUALITY_ISSUE', label: '质量问题' },
  { value: 'NOT_AS_DESCRIBED', label: '与描述不符' },
  { value: 'DAMAGED', label: '运输破损' },
  { value: 'WRONG_ITEM', label: '发错货' },
  { value: 'NO_LONGER_NEEDED', label: '不想要了' },
  { value: 'INSTALL_ISSUE', label: '安装问题' },
  { value: 'OTHER', label: '其他' },
];
