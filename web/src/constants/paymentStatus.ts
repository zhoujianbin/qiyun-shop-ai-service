import type { PaymentStatus, PayStatus, PaymentMethod } from '@/types/status';

export const PAYMENT_STATUS_LABELS: Record<PaymentStatus, string> = {
  UNPAID: '未支付', PARTIAL: '部分支付', PAID: '已支付',
  REFUNDING: '退款中', PARTIAL_REFUNDED: '部分退款', REFUNDED: '已退款',
};
export const PAYMENT_STATUS_COLORS: Record<PaymentStatus, string> = {
  UNPAID: 'warning', PARTIAL: 'warning', PAID: 'success',
  REFUNDING: 'processing', PARTIAL_REFUNDED: 'processing', REFUNDED: 'default',
};
export const PAYMENT_STATUS_OPTIONS = (Object.keys(PAYMENT_STATUS_LABELS) as PaymentStatus[]).map((value) => ({
  value, label: PAYMENT_STATUS_LABELS[value],
}));

export const PAY_STATUS_LABELS: Record<PayStatus, string> = {
  PENDING: '待支付', SUCCESS: '支付成功', FAILED: '支付失败', CLOSED: '已关闭',
};
export const PAY_STATUS_OPTIONS = (Object.keys(PAY_STATUS_LABELS) as PayStatus[]).map((value) => ({
  value, label: PAY_STATUS_LABELS[value],
}));

export const PAYMENT_METHOD_LABELS: Record<PaymentMethod, string> = {
  MOCK: '模拟支付', WECHAT_PAY: '微信支付', ALIPAY: '支付宝', UNIONPAY: '银联', BALANCE: '余额支付',
};
export const PAYMENT_METHOD_OPTIONS = (Object.keys(PAYMENT_METHOD_LABELS) as PaymentMethod[]).map((value) => ({
  value, label: PAYMENT_METHOD_LABELS[value],
}));
