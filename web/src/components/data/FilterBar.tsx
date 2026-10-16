import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Space from 'antd/es/space';
import ReloadOutlined from '@ant-design/icons/ReloadOutlined';
import SearchOutlined from '@ant-design/icons/SearchOutlined';
import type { ReactNode } from 'react';

export interface FilterBarProps {
  children: ReactNode;
  onSearch?: () => void;
  onReset?: () => void;
  extra?: ReactNode;
  loading?: boolean;
}

/** 声明式筛选区：字段标签可见，重置与查询明确。 */
export function FilterBar({ children, onSearch, onReset, extra, loading }: FilterBarProps) {
  return (
    <Card size="small" style={{ marginBottom: 12 }} styles={{ body: { padding: 12 } }}>
      <Space size={12} wrap align="end">
        {children}
        <Space size={8}>
          {onSearch ? (
            <Button type="primary" icon={<SearchOutlined />} onClick={onSearch} loading={loading}>
              查询
            </Button>
          ) : null}
          {onReset ? (
            <Button icon={<ReloadOutlined />} onClick={onReset}>
              重置
            </Button>
          ) : null}
          {extra}
        </Space>
      </Space>
    </Card>
  );
}
