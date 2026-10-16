import Empty from 'antd/es/empty';
import Space from 'antd/es/space';
import Typography from 'antd/es/typography';
import type { ReactNode } from 'react';

export interface EmptyStateProps {
  title?: string;
  description?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
}

export function EmptyState({ title = '暂无数据', description, action, compact }: EmptyStateProps) {
  return (
    <div role="status" aria-live="polite" style={{ padding: compact ? 16 : 32, textAlign: 'center' }}>
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          <Space direction="vertical" size={4}>
            <Typography.Text strong>{title}</Typography.Text>
            {description ? <Typography.Text type="secondary">{description}</Typography.Text> : null}
          </Space>
        }
      >
        {action}
      </Empty>
    </div>
  );
}
