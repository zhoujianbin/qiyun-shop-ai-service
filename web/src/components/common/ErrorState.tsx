import Alert from 'antd/es/alert';
import App from 'antd/es/app';
import Button from 'antd/es/button';
import Space from 'antd/es/space';
import Typography from 'antd/es/typography';
import CopyOutlined from '@ant-design/icons/CopyOutlined';
import ReloadOutlined from '@ant-design/icons/ReloadOutlined';
import { toApiError } from '@/api/errors';

export interface ErrorStateProps {
  title?: string;
  error?: unknown;
  requestId?: string;
  onRetry?: () => void;
  extra?: React.ReactNode;
  compact?: boolean;
}

export function ErrorState({ title = '加载失败', error, requestId, onRetry, extra, compact }: ErrorStateProps) {
  const { message } = App.useApp();
  const apiError = error ? toApiError(error) : undefined;
  const rid = requestId ?? apiError?.requestId;

  const copyRequestId = () => {
    if (!rid) return;
    void navigator.clipboard.writeText(rid).then(
      () => message.success('request_id 已复制'),
      () => message.error('复制失败，请手动选择'),
    );
  };

  return (
    <div role="alert" style={{ padding: compact ? 12 : 24 }}>
      <Alert
        type="error"
        showIcon
        message={title}
        description={
          <Space direction="vertical" size={6} style={{ width: '100%' }}>
            <Typography.Text>{apiError?.message ?? '请求失败，请稍后重试'}</Typography.Text>
            {rid ? (
              <Space size={6}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  request_id: <Typography.Text code>{rid}</Typography.Text>
                </Typography.Text>
                <Button type="link" size="small" icon={<CopyOutlined />} onClick={copyRequestId}>
                  复制
                </Button>
              </Space>
            ) : null}
            <Space>
              {onRetry ? (
                <Button icon={<ReloadOutlined />} onClick={onRetry} type="primary" ghost>
                  重试
                </Button>
              ) : null}
              {extra}
            </Space>
          </Space>
        }
      />
    </div>
  );
}
