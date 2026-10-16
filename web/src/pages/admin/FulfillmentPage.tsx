import App from 'antd/es/app';
import Button from 'antd/es/button';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ordersApi } from '@/api/endpoints/orders';
import { shipmentsApi } from '@/api/endpoints/shipments';
import { warehousesApi } from '@/api/endpoints/warehouses';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { DataTable } from '@/components/data/DataTable';
import { PageHeader } from '@/components/common/PageHeader';
import { PermissionGate } from '@/components/common/PermissionGate';
import { StatusTag } from '@/components/common/StatusTag';
import { MoneyText } from '@/components/common/MoneyText';
import { ShipDialog } from '@/components/order/ShipDialog';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { useChannelScope } from '@/hooks/useChannelScope';
import { errorMessage } from '@/api/errors';
import { formatDateTime } from '@/utils/datetime';
import { P } from '@/types/permissions';
import type { Order, ShipRequest } from '@/types/domain';

/** B 端履约发货：待发货订单队列 + 发货弹窗（支持部分发货）。 */
export default function FulfillmentPage() {
  const { message } = App.useApp();
  const { activeChannelId } = useChannelScope();
  const [status, setStatus] = useState<string>('PAID');
  const [shipOrder, setShipOrder] = useState<Order | null>(null);

  const query = useQuery({
    queryKey: queryKeys.orders.list({ status, channel_account_id: activeChannelId ?? undefined, page: 1, page_size: 50 }),
    queryFn: ({ signal }) => ordersApi.list({ status, channel_account_id: activeChannelId ?? undefined, page: 1, page_size: 50, signal }),
  });
  const warehouseQuery = useQuery({
    queryKey: queryKeys.warehouses.list({ page: 1, page_size: 100 }),
    queryFn: ({ signal }) => warehousesApi.list({ page: 1, page_size: 100, signal }),
  });
  const carrierQuery = useQuery({
    queryKey: queryKeys.carriers.list(),
    queryFn: ({ signal }) => shipmentsApi.carriers({ signal }),
  });

  const shipMutation = useIdempotentMutation((vars: { id: number; body: ShipRequest }) => ordersApi.ship(vars.id, vars.body), {
    onSuccess: async () => {
      message.success('发货成功');
      setShipOrder(null);
      shipMutation.resetKey();
      await queryClient.invalidateQueries({ queryKey: ['orders'] });
      await queryClient.invalidateQueries({ queryKey: ['shipments'] });
      await queryClient.invalidateQueries({ queryKey: ['inventory'] });
    },
    onError: (error) => message.error(errorMessage(error)),
  });

  const columns: ColumnsType<Order> = [
    { title: '订单号', dataIndex: 'order_no', key: 'order_no' },
    { title: '收件人', dataIndex: 'receiver_name', key: 'receiver_name' },
    { title: '应付', dataIndex: 'payable_amount', key: 'payable_amount', render: (value: string) => <MoneyText value={value} /> },
    { title: '订单状态', dataIndex: 'status', key: 'status', render: (value: string) => <StatusTag kind="order" value={value} /> },
    { title: '履约', dataIndex: 'fulfillment_status', key: 'fulfillment_status', render: (value: string) => <StatusTag kind="fulfillment" value={value} /> },
    { title: '下单时间', dataIndex: 'created_at', key: 'created_at', render: (value: string) => formatDateTime(value) },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_, record) => (
        <PermissionGate permission={P.fulfillmentWrite} mode="disable" fallbackReason="需要履约写权限">
          <Button type="link" onClick={() => setShipOrder(record)}>发货</Button>
        </PermissionGate>
      ),
    },
  ];

  return (
    <div className="qy-page">
      <PageHeader
        title="履约发货"
        subtitle="待发货订单队列，支持按包裹部分发货"
        extra={
          <Select
            style={{ width: 180 }}
            value={status}
            onChange={setStatus}
            options={[
              { value: 'PAID', label: '待发货（已支付）' },
              { value: 'FULFILLING', label: '备货中' },
            ]}
          />
        }
      />
      <DataTable<Order>
        rowKey="id"
        columns={columns}
        data={query.data?.items ?? []}
        loading={query.isLoading}
        error={query.error}
        onRetry={() => void query.refetch()}
        showPagination={false}
        emptyTitle="当前没有待发货订单"
        emptyDescription="订单支付后会自动进入该队列"
        toolbar={<Typography.Text type="secondary">发货将扣减对应仓库可售库存并生成包裹与运单。</Typography.Text>}
      />
      <ShipDialog
        open={Boolean(shipOrder)}
        order={shipOrder}
        warehouses={warehouseQuery.data?.items ?? []}
        carriers={carrierQuery.data?.items ?? []}
        loading={shipMutation.isPending}
        onCancel={() => setShipOrder(null)}
        onSubmit={(payload) => shipOrder && shipMutation.mutate({ id: shipOrder.id, body: payload })}
      />
    </div>
  );
}
