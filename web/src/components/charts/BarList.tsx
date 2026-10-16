import Space from 'antd/es/space';
import Typography from 'antd/es/typography';
import { formatMoney } from '@/utils/money';

export interface BarListItem {
  label: string;
  value: number;
  /** 是否以金额展示 */
  money?: boolean;
}

export interface BarListProps {
  items: BarListItem[];
  max?: number;
}

/** 轻量排行条形图：无图表库依赖，颜色+文字双重编码，可无障碍阅读。 */
export function BarList({ items, max }: BarListProps) {
  const peak = max ?? Math.max(1, ...items.map((item) => item.value));
  if (items.length === 0) return <Typography.Text type="secondary">暂无数据</Typography.Text>;
  return (
    <Space direction="vertical" size={8} style={{ width: '100%' }}>
      {items.map((item) => (
        <div key={item.label}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
            <Typography.Text ellipsis style={{ maxWidth: '65%' }}>{item.label}</Typography.Text>
            <Typography.Text strong>{item.money ? formatMoney(String(item.value / 100)) : item.value}</Typography.Text>
          </div>
          <div style={{ height: 8, borderRadius: 4, background: '#EEF3FF', marginTop: 4 }}>
            <div style={{ width: `${Math.min(100, (item.value / peak) * 100)}%`, height: 8, borderRadius: 4, background: '#1F5EFF' }} />
          </div>
        </div>
      ))}
    </Space>
  );
}
