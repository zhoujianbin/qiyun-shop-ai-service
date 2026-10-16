import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import type { ColumnsType } from 'antd/es/table';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { afterSalesApi } from '@/api/endpoints/afterSales';
import { queryKeys } from '@/api/queryKeys';
import { DataTable } from '@/components/data/DataTable';
import { FilterBar } from '@/components/data/FilterBar';
import { PageHeader } from '@/components/common/PageHeader';
import { StatusTag } from '@/components/common/StatusTag';
import { MoneyText } from '@/components/common/MoneyText';
import { useUrlFilters } from '@/hooks/useUrlFilters';
import { useChannelScope } from '@/hooks/useChannelScope';
import { formatDateTime } from '@/utils/datetime';
import { AFTER_SALES_STATUS_OPTIONS, AFTER_SALES_TYPE_OPTIONS } from '@/constants/statusMaps';
import { ROUTES } from '@/constants/routes';
import type { AfterSalesApplication } from '@/types/domain';

interface TicketFilters extends Record<string, string | undefined> {
  status?: string;
  type?: string;
  order_id?: string;
}

/** B 端售后工单列表。 */
export default function AfterSalesPage() {
  const navigate = useNavigate();
  const { activeChannelId } = useChannelScope();
  const url = useUrlFilters<TicketFilters>({ status: undefined, type: undefined, order_id: undefined });

  const params = {
    status: url.filters.status,
    type: url.filters.type,
    order_id: url.filters.order_id,
    channel_account_id: activeChannelId ?? undefined,
    page: url.page,
    page_size: url.pageSize,
  };

  const query = useQuery({
    queryKey: queryKeys.afterSales.list(params),
    queryFn: ({ signal }) => afterSalesApi.list({ ...params, signal }),
  });

  const columns: ColumnsType<AfterSalesApplication> = [
    { title: '售后单号', dataIndex: 'application_no', key: 'application_no', render: (value: string, record) => <a onClick={() => navigate(ROUTES.adminAfterSalesTicket(record.id))}>{value}</a> },
    { title: '订单号', dataIndex: 'order_no', key: 'order_no', render: (value?: string) => value ?? '-' },
    { title: '类型', dataIndex: 'type', key: 'type', render: (value: string) => <StatusTag kind="afterSalesType" value={value} /> },
    { title: '状态', dataIndex: 'status', key: 'status', render: (value: string) => <StatusTag kind="afterSales" value={value} /> },
    { title: '退款金额', dataIndex: 'refund_amount', key: 'refund_amount', render: (value?: string) => <MoneyText value={value} /> },
    { title: '原因码', dataIndex: 'reason_code', key: 'reason_code', render: (value?: string) => value ?? '-' },
    { title: '申请时间', dataIndex: 'applied_at', key: 'applied_at', render: (value: string) => formatDateTime(value) },
    {
      title: '操作',
      key: 'action',
      width: 110,
      render: (_, record) => <Button type="link" onClick={() => navigate(ROUTES.adminAfterSalesTicket(record.id))}>处理</Button>,
    },
  ];

  return (
    <div className="qy-page">
      <PageHeader title="售后工单" subtitle="退换修工单受理与审核" />
      <FilterBar onReset={() => url.reset()}>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">状态</span>
          <Select allowClear style={{ width: 160 }} placeholder="全部" value={url.filters.status} options={AFTER_SALES_STATUS_OPTIONS} onChange={(value) => url.setFilter('status', value)} />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">类型</span>
          <Select allowClear style={{ width: 150 }} placeholder="全部" value={url.filters.type} options={AFTER_SALES_TYPE_OPTIONS} onChange={(value) => url.setFilter('type', value)} />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">订单 ID</span>
          <Input.Search allowClear style={{ width: 160 }} placeholder="精确" defaultValue={url.filters.order_id} onSearch={(value) => url.setFilter('order_id', value || undefined)} />
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
        page={url.page}
        pageSize={url.pageSize}
        onPageChange={(page, pageSize) => { url.setPage(page); if (pageSize !== url.pageSize) url.setPageSize(pageSize); }}
        emptyTitle="暂无售后工单"
      />
    </div>
  );
}
