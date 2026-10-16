import Button from 'antd/es/button';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Table from 'antd/es/table';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { Link, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { afterSalesApi } from '@/api/endpoints/afterSales';
import { queryKeys } from '@/api/queryKeys';
import { PageHeader } from '@/components/common/PageHeader';
import { StatusTag } from '@/components/common/StatusTag';
import { MoneyText } from '@/components/common/MoneyText';
import { DataTable } from '@/components/data/DataTable';
import { FilterBar } from '@/components/data/FilterBar';
import { useAuthStore } from '@/stores/authStore';
import { formatDateTime } from '@/utils/datetime';
import { AFTER_SALES_STATUS_OPTIONS } from '@/constants/statusMaps';
import { ROUTES } from '@/constants/routes';
import type { AfterSalesApplication } from '@/types/domain';

/** C 端售后列表与详情入口。 */
export default function AfterSalesListPage() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const [status, setStatus] = useState<string | undefined>();
  const [page, setPage] = useState(1);
  const pageSize = 10;

  const query = useQuery({
    queryKey: queryKeys.afterSales.list({ customer_id: user?.id, status, page, page_size: pageSize }),
    queryFn: ({ signal }) => afterSalesApi.list({ customer_id: user?.id, status, page, page_size: pageSize, signal }),
    enabled: Boolean(user?.id),
  });

  const columns: ColumnsType<AfterSalesApplication> = [
    { title: '售后单号', dataIndex: 'application_no', key: 'application_no', render: (value: string, record) => <Link to={ROUTES.afterSalesDetail(record.id)}>{value}</Link> },
    { title: '订单号', dataIndex: 'order_no', key: 'order_no', render: (value?: string) => value ?? '-' },
    { title: '类型', dataIndex: 'type', key: 'type', render: (value: string) => <StatusTag kind="afterSalesType" value={value} /> },
    { title: '状态', dataIndex: 'status', key: 'status', render: (value: string) => <StatusTag kind="afterSales" value={value} /> },
    { title: '退款金额', dataIndex: 'refund_amount', key: 'refund_amount', render: (value?: string) => <MoneyText value={value} /> },
    { title: '申请时间', dataIndex: 'applied_at', key: 'applied_at', render: (value: string) => formatDateTime(value) },
  ];

  return (
    <div className="qy-page" style={{ maxWidth: 1000, margin: '0 auto' }}>
      <PageHeader
        title="售后服务"
        subtitle="退换修申请与处理进度"
        extra={<Button type="primary" onClick={() => navigate(ROUTES.afterSalesApply)}>申请售后</Button>}
      />
      <FilterBar onReset={() => { setStatus(undefined); setPage(1); }}>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">售后状态</span>
          <Select
            allowClear
            placeholder="全部"
            style={{ width: 180 }}
            value={status}
            options={AFTER_SALES_STATUS_OPTIONS}
            onChange={(value) => { setStatus(value); setPage(1); }}
          />
        </Space>
      </FilterBar>
      <DataTable<AfterSalesApplication>
        rowKey="id"
        columns={columns}
        data={query.data?.items ?? []}
        loading={query.isLoading}
        error={query.error}
        onRetry={() => void query.refetch()}
        total={query.data?.meta?.total ?? 0}
        page={page}
        pageSize={pageSize}
        onPageChange={(next) => setPage(next)}
        emptyTitle="暂无售后记录"
        emptyAction={
          <Space>
            <Typography.Text type="secondary">如有商品问题可发起售后申请</Typography.Text>
            <Button type="primary" onClick={() => navigate(ROUTES.afterSalesApply)}>申请售后</Button>
          </Space>
        }
      />
    </div>
  );
}
