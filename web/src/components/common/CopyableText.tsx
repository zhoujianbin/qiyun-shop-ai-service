import App from 'antd/es/app';
import Typography from 'antd/es/typography';
import CopyOutlined from '@ant-design/icons/CopyOutlined';

export interface CopyableTextProps {
  value?: string | null;
  label?: string;
  strong?: boolean;
}

export function CopyableText({ value, label, strong }: CopyableTextProps) {
  const { message } = App.useApp();
  if (!value) return <span>-</span>;
  const copy = () => {
    void navigator.clipboard.writeText(value).then(
      () => message.success(`${label ?? '内容'} 已复制`),
      () => message.error('复制失败，请手动选择'),
    );
  };
  return (
    <Typography.Text strong={strong} copyable={{ text: value, icon: <CopyOutlined />, tooltips: ['复制', '已复制'] }} onClick={copy}>
      {value}
    </Typography.Text>
  );
}
