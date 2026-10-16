import type { Order } from '@/types/domain';

export type OrderAction = 'ship' | 'cancel' | 'confirmReceipt' | 'editAddress' | 'editRemark' | 'refund' | 'invoice' | 'afterSales';

/** 状态机驱动的动作可用性（前端仅做展示裁剪，权威在后端）。 */
export function canOrderAction(order: Order | null | undefined, action: OrderAction): boolean {
  if (!order) return false;
  const { status, payment_status: paymentStatus, fulfillment_status: fulfillmentStatus } = order;
  switch (action) {
    case 'ship':
      return ['PAID', 'FULFILLING'].includes(status) && fulfillmentStatus !== 'SHIPPED' && fulfillmentStatus !== 'DELIVERED';
    case 'cancel':
      return ['CREATED', 'PENDING_PAYMENT'].includes(status);
    case 'confirmReceipt':
      return status === 'SHIPPED';
    case 'editAddress':
      return ['CREATED', 'PENDING_PAYMENT', 'PAID'].includes(status) && fulfillmentStatus === 'UNSHIPPED';
    case 'editRemark':
      return !['COMPLETED', 'CANCELLED', 'CLOSED'].includes(status);
    case 'refund':
      return ['PAID', 'PARTIAL'].includes(paymentStatus);
    case 'invoice':
      return status === 'COMPLETED';
    case 'afterSales':
      return ['SHIPPED', 'COMPLETED'].includes(status);
    default:
      return false;
  }
}
