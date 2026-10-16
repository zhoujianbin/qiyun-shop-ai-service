import Timeline from 'antd/es/timeline';
import Typography from 'antd/es/typography';
import { LoadingSkeleton } from '../common/LoadingSkeleton';
import { ErrorState } from '../common/ErrorState';
import { EmptyState } from '../common/EmptyState';
import { CopyableText } from '../common/CopyableText';
import { formatDateTime } from '@/utils/datetime';
import type { OrderTimelineEntry } from '@/types/domain';
import {
  FULFILLMENT_STATUS_LABELS, ORDER_AFTER_SALES_STATUS_LABELS, ORDER_STATUS_LABELS,
  PAYMENT_STATUS_LABELS,
} from '@/constants/statusMaps';

export interface OrderTimelineProps {
  events: OrderTimelineEntry[];
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
}

const FIELD_LABELS: Record<OrderTimelineEntry['field'], string> = {
  status: '订单状态',
  payment_status: '支付状态',
  fulfillment_status: '履约状态',
  after_sales_status: '售后状态',
};

function labelOf(field: OrderTimelineEntry['field'], value?: string | null): string {
  if (!value) return '-';
  switch (field) {
    case 'status':
      return ORDER_STATUS_LABELS[value as keyof typeof ORDER_STATUS_LABELS] ?? value;
    case 'payment_status':
      return PAYMENT_STATUS_LABELS[value as keyof typeof PAYMENT_STATUS_LABELS] ?? value;
    case 'fulfillment_status':
      return FULFILLMENT_STATUS_LABELS[value as keyof typeof FULFILLMENT_STATUS_LABELS] ?? value;
    case 'after_sales_status':
      return ORDER_AFTER_SALES_STATUS_LABELS[value as keyof typeof ORDER_AFTER_SALES_STATUS_LABELS] ?? value;
    default:
      return value;
  }
}

/** 订单事件时间线：每项含操作者、时间、可复制的 request_id。 */
export function OrderTimeline({ events, loading, error, onRetry }: OrderTimelineProps) {
  if (loading) return <LoadingSkeleton rows={4} />;
  if (error) return <ErrorState error={error} onRetry={onRetry} compact />;
  if (events.length === 0) return <EmptyState title="暂无时间线记录" compact />;

  return (
    <div role="list" aria-label="订单状态时间线">
      <Timeline
        items={events.map((entry) => ({
          children: (
            <div role="listitem">
              <Typography.Text strong>
                {FIELD_LABELS[entry.field]}：{labelOf(entry.field, entry.from_value)} → {labelOf(entry.field, entry.to_value)}
              </Typography.Text>
              <div>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {formatDateTime(entry.created_at)} · {entry.operator_type ?? 'SYSTEM'}
                  {entry.reason ? ` · ${entry.reason}` : ''}
                </Typography.Text>
              </div>
              <div>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  request_id: <CopyableText value={String(entry.id)} label="request_id" />
                </Typography.Text>
              </div>
            </div>
          ),
        }))}
      />
    </div>
  );
}
