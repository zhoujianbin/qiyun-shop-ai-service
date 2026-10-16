import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Tag from 'antd/es/tag';
import Typography from 'antd/es/typography';
import { useChannelScope } from '@/hooks/useChannelScope';

/** 渠道范围切换：常驻后台顶栏；只有一个渠道时仍展示但不可切换。 */
export function ChannelScopeSelect() {
  const { available, activeIds, setActive, isLoading } = useChannelScope();

  if (isLoading) return <Typography.Text type="secondary">渠道加载中…</Typography.Text>;
  if (available.length === 0) return <Tag>无渠道授权</Tag>;

  return (
    <Space size={6}>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        渠道范围
      </Typography.Text>
      <Select
        mode="multiple"
        size="small"
        style={{ minWidth: 220 }}
        loading={isLoading}
        value={activeIds}
        disabled={available.length <= 1}
        placeholder="选择渠道范围"
        onChange={(values: number[]) => setActive(values)}
        options={available.map((channel) => ({ value: channel.id, label: channel.name }))}
        maxTagCount={2}
      />
    </Space>
  );
}
