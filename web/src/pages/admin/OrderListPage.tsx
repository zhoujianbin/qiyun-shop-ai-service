import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Table from 'antd/es/table';
import Tabs from 'antd/es/tabs';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ordersApi } from '@/api/endpoints/orders';
import { queryKeys } from '@/api/queryKeys';
import { DataTable } from '@/components/data/DataTable';
import { FilterBar } from '@/components/data/FilterBar';
import { PageHeader } from '@/components/common/PageHeader';
import { PermissionGate } from '@/components/common/PermissionGate';
import { StatusTag } from '@/components/common/StatusTag';
import { MoneyText } from '@/components/common/MoneyText';
import { CopyableText } from '@/components/common/CopyableText';
import { MaskedText } from '@/components/common/MaskedText';
import { useUrlFilters } from '@/hooks/useUrlFilters';
import { useChannelScope } from '@/hooks/useChannelScope';
import { canOrderAction } from '@/utils/orderActions';
import { formatDateTime } from '@/utils/datetime';
import { ORDER_STATUS_OPTIONS, PAYMENT_STATUS_OPTIONS, FULFILLMENT_STATUS_OPTIONS, ORDER_AFTER_SALES_STATUS_OPTIONS } from '@/constants/statusMaps';
import { P } from '@/types/permissions';
import { ROUTES } from '@/constants/routes';
import type { Order } from '@/types/domain';

interface OrderFilters extends Record<string, string | undefined> {
  order_no?: string;
  status?: string;
  payment_status?: string;
  fulfillment_status?: string;
  after_sales_status?: string;
}

const TABS = [{ value: '', label: '全部' }, ...ORDER_STATUS_OPTIONS];

/** B 端订单列表：多状态筛选、展开商品明细、渠道范围过滤。 */
export default function OrderListPage() {
  const navigate = useNavigate();
  const { activeChannelId } = useChannelScope();
  const url = useUrlFilters<OrderFilters>({ order_no: undefined, status: undefined, payment_status: undefined, fulfillment_status: undefined, after_sales_status: undefined });

  const params = {
    order_no: url.filters.order_no,
    status: url.filters.status,
    payment_status: url.filters.payment_status,
    fulfillment_status: url.filters.fulfillment_status,
    after_sales_status: url.filters.after_sales_status,
    channel_account_id: activeChannelId ?? undefined,
    page: url.page,
    page_size: url.pageSize,
  };

  const query = useQuery({
    queryKey: queryKeys.orders.list(params),
    queryFn: ({ signal }) => ordersApi.list({ ...params, signal }),
  });

  const columns: ColumnsType<Order> = [
    { title: '订单号', dataIndex: 'order_no', key: 'order_no', render: (value: string) => <CopyableText value={value} label="订单号" strong /> },
    {
      title: '客户',
      key: 'customer',
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Typography.Text>{record.receiver_name ?? '-'}</Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}><MaskedText value={record.receiver_phone_masked} /></Typography.Text>
        </Space>
      ),
    },
    {
      title: '金额',
      key: 'amount',
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <MoneyText value={record.payable_amount} strong />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>实付 <MoneyText value={record.paid_amount} muted /></Typography.Text>
        </Space>
      ),
    },
    {
      title: '状态',
      key: 'status',
      render: (_, record) => (
        <Space size={4} wrap>
          <StatusTag kind="order" value={record.status} />
          <StatusTag kind="payment" value={record.payment_status} />
          <StatusTag kind="fulfillment" value={record.fulfillment_status} />
          <StatusTag kind="orderAfterSales" value={record.after_sales_status} />
        </Space>
      ),
    },
    { title: '下单时间', dataIndex: 'created_at', key: 'created_at', render: (value: string) => formatDateTime(value) },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_, record) => (
        <Space>
          <Button type="link" onClick={() => navigate(ROUTES.adminOrderDetail(record.order_no))}>查看</Button>
          {canOrderAction(record, 'ship') ? (
            <PermissionGate permission={P.fulfillmentWrite} mode="disable" fallbackReason="需要履约写权限">
              <Button type="link" onClick={() => navigate(`${ROUTES.adminOrderDetail(record.order_no)}?action=ship`)}>发货</Button>
            </PermissionGate>
          ) : null}
        </Space>
      ),
    },
  ];

  return (
    <div className="qy-page">
      <PageHeader title="订单管理" subtitle="订单/支付/履约/售后四态筛选与处置" />
      <Tabs
        activeKey={url.filters.status ?? ''}
        onChange={(key) => url.patchFilters({ status: key || undefined })}
        items={TABS.map((tab) => ({ key: tab.value, label: tab.label }))}
      />
      <FilterBar onReset={() => url.reset()}>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">订单号</span>
          <Input.Search allowClear style={{ width: 200 }} placeholder="精确" defaultValue={url.filters.order_no} onSearch={(value) => url.setFilter('order_no', value || undefined)} />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">支付状态</span>
          <Select allowClear style={{ width: 150 }} placeholder="全部" value={url.filters.payment_status} options={PAYMENT_STATUS_OPTIONS} onChange={(value) => url.setFilter('payment_status', value)} />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">履约状态</span>
          <Select allowClear style={{ width: 150 }} placeholder="全部" value={url.filters.fulfillment_status} options={FULFILLMENT_STATUS_OPTIONS} onChange={(value) => url.setFilter('fulfillment_status', value)} />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">售后状态</span>
          <Select allowClear style={{ width: 150 }} placeholder="全部" value={url.filters.after_sales_status} options={ORDER_AFTER_SALES_STATUS_OPTIONS} onChange={(value) => url.setFilter('after_sales_status', value)} />
        </Space>
      </FilterBar>
      <DataTable<Order>
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
        emptyTitle="暂无订单"
        emptyDescription="可重置筛选条件后重试"
        scrollX={1200}
        expandable={{
          expandedRowRender: (record) => (
            <Table
              size="small"
              rowKey="id"
              pagination={false}
              dataSource={record.items ?? []}
              columns={[
                { title: '商品', dataIndex: 'product_name', key: 'product_name' },
                { title: '规格', dataIndex: 'sku_name', key: 'sku_name' },
                { title: '单价', dataIndex: 'unit_price', key: 'unit_price', render: (value: string) => <MoneyText value={value} /> },
                { title: '数量', dataIndex: 'quantity', key: 'quantity' },
                { title: '应付', dataIndex: 'payable_amount', key: 'payable_amount', render: (value: string) => <MoneyText value={value} /> },
              ]}
            />
          ),
        }}
      />
    </div>
  );
}
