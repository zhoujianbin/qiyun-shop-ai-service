import Card from 'antd/es/card';
import Statistic from 'antd/es/statistic';
import Typography from 'antd/es/typography';
import type { ReactNode } from 'react';
import { ErrorState } from './ErrorState';

export interface StatCardProps {
  title: string;
  value?: ReactNode;
  suffix?: ReactNode;
  prefix?: ReactNode;
  precision?: number;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  hint?: ReactNode;
}

/** 指标卡：工作台与报表概览使用；支持 loading / error / 空值。 */
export function StatCard({ title, value, suffix, prefix, precision, loading, error, onRetry, hint }: StatCardProps) {
  if (error) {
    return (
      <Card>
        <Typography.Text type="secondary">{title}</Typography.Text>
        <ErrorState error={error} onRetry={onRetry} compact />
      </Card>
    );
  }
  return (
    <Card>
      <Statistic title={title} value={value as string | number} precision={precision} suffix={suffix} prefix={prefix} loading={loading} />
      {hint ? (
        <div style={{ marginTop: 4 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {hint}
          </Typography.Text>
        </div>
      ) : null}
    </Card>
  );
}
