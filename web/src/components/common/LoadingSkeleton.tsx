import Skeleton from 'antd/es/skeleton';
import Space from 'antd/es/space';

export interface LoadingSkeletonProps {
  rows?: number;
  active?: boolean;
  title?: boolean;
}

export function LoadingSkeleton({ rows = 6, active = true, title = true }: LoadingSkeletonProps) {
  return (
    <div style={{ padding: 16 }} aria-busy="true" aria-live="polite">
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        {title ? <Skeleton.Input active={active} block style={{ height: 24, maxWidth: 320 }} /> : null}
        <Skeleton active={active} paragraph={{ rows }} title={false} />
      </Space>
    </div>
  );
}
