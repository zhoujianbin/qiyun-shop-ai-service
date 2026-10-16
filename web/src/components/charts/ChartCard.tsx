import Card from 'antd/es/card';
import Empty from 'antd/es/empty';
import Typography from 'antd/es/typography';
import type { ReactNode } from 'react';
import { ErrorState } from '../common/ErrorState';
import { LoadingSkeleton } from '../common/LoadingSkeleton';

export interface ChartCardProps {
  title: string;
  description?: string;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  empty?: boolean;
  summary?: string;
  extra?: ReactNode;
  children: ReactNode;
}

/** 图表/指标卡容器：统一 loading/error/empty，并提供可访问文本摘要。 */
export function ChartCard({ title, description, loading, error, onRetry, empty, summary, extra, children }: ChartCardProps) {
  return (
    <Card
      title={
        <span>
          {title}
          {description ? (
            <Typography.Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
              {description}
            </Typography.Text>
          ) : null}
        </span>
      }
      extra={extra}
      styles={{ body: { minHeight: 120 } }}
    >
      {loading ? (
        <LoadingSkeleton rows={3} title={false} />
      ) : error ? (
        <ErrorState error={error} onRetry={onRetry} compact />
      ) : empty ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无数据" />
      ) : (
        <figure style={{ margin: 0 }}>
          {children}
          {summary ? (
            <figcaption role="note" aria-label={`${title}文本摘要`} style={{ marginTop: 8, color: '#6B7280', fontSize: 12 }}>
              {summary}
            </figcaption>
          ) : null}
        </figure>
      )}
    </Card>
  );
}
