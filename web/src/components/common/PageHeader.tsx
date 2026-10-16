import Breadcrumb from 'antd/es/breadcrumb';
import Space from 'antd/es/space';
import Typography from 'antd/es/typography';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

export interface BreadcrumbItem {
  label: string;
  to?: string;
}

export interface PageHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  breadcrumb?: BreadcrumbItem[];
  extra?: ReactNode;
  tags?: ReactNode;
}

export function PageHeader({ title, subtitle, breadcrumb, extra, tags }: PageHeaderProps) {
  return (
    <div style={{ marginBottom: 16 }}>
      {breadcrumb && breadcrumb.length > 0 ? (
        <nav aria-label="面包屑">
          <Breadcrumb
            style={{ marginBottom: 8 }}
            items={breadcrumb.map((item) => ({
              title: item.to ? <Link to={item.to}>{item.label}</Link> : item.label,
            }))}
          />
        </nav>
      ) : null}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
        <div>
          <Space size={8} align="center" wrap>
            <Typography.Title level={1} style={{ margin: 0, fontSize: 22 }}>
              {title}
            </Typography.Title>
            {tags}
          </Space>
          {subtitle ? (
            <div style={{ marginTop: 4 }}>
              <Typography.Text type="secondary">{subtitle}</Typography.Text>
            </div>
          ) : null}
        </div>
        {extra ? <Space wrap>{extra}</Space> : null}
      </div>
    </div>
  );
}
