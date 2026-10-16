import type { FulfillmentStatus, ShipmentStatus } from '@/types/status';

export const FULFILLMENT_STATUS_LABELS: Record<FulfillmentStatus, string> = {
  UNSHIPPED: '未发货', PARTIAL_SHIPPED: '部分发货', SHIPPED: '已发货', DELIVERED: '已签收',
};
export const FULFILLMENT_STATUS_COLORS: Record<FulfillmentStatus, string> = {
  UNSHIPPED: 'default', PARTIAL_SHIPPED: 'warning', SHIPPED: 'processing', DELIVERED: 'success',
};
export const FULFILLMENT_STATUS_OPTIONS = (Object.keys(FULFILLMENT_STATUS_LABELS) as FulfillmentStatus[]).map((value) => ({
  value, label: FULFILLMENT_STATUS_LABELS[value],
}));

export const SHIPMENT_STATUS_LABELS: Record<ShipmentStatus, string> = {
  PENDING: '待揽收', PICKED_UP: '已揽收', IN_TRANSIT: '运输中',
  DELIVERED: '已签收', EXCEPTION: '异常', RETURNED: '已退回',
};
export const SHIPMENT_STATUS_OPTIONS = (Object.keys(SHIPMENT_STATUS_LABELS) as ShipmentStatus[]).map((value) => ({
  value, label: SHIPMENT_STATUS_LABELS[value],
}));
