import Button from 'antd/es/button';
import Descriptions from 'antd/es/descriptions';
import Space from 'antd/es/space';
import Tabs from 'antd/es/tabs';
import Typography from 'antd/es/typography';
import { Link, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ordersApi } from '@/api/endpoints/orders';
import { queryKeys } from '@/api/queryKeys';
import { PageHeader } from '@/components/common/PageHeader';
import { EmptyState } from '@/components/common/EmptyState';
import { ErrorState } from '@/components/common/ErrorState';
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton';
import { MoneyText } from '@/components/common/MoneyText';
import { StatusTag } from '@/components/common/StatusTag';
import { useAuthStore } from '@/stores/authStore';
import { formatDateTime } from '@/utils/datetime';
import { ORDER_STATUS_OPTIONS } from '@/constants/statusMaps';
import { ROUTES } from '@/constants/routes';

const TABS = [{ value: '', label: '全部' }, ...ORDER_STATUS_OPTIONS];

/** C 端订单列表：状态 Tab + 分页，仅本人订单。 */
export default function OrderListPage() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 10;

  const query = useQuery({
    queryKey: queryKeys.orders.list({ customer_id: user?.id, status, page, page_size: pageSize }),
    queryFn: ({ signal }) => ordersApi.list({ customer_id: user?.id, status: status || undefined, page, page_size: pageSize, signal }),
    enabled: Boolean(user?.id),
  });

  const orders = query.data?.items ?? [];
  const total = query.data?.meta?.total ?? 0;

  return (
    <div className="qy-page" style={{ maxWidth: 1000, margin: '0 auto' }}>
      <PageHeader title="我的订单" subtitle="查看订单状态、物流与售后进度" />
      <Tabs
        activeKey={status}
        onChange={(key) => {
          setStatus(key);
          setPage(1);
        }}
        items={TABS.map((tab) => ({ key: tab.value, label: tab.label }))}
      />
      {query.isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : orders.length === 0 ? (
        <EmptyState title="暂无订单" description="快去挑选商品下单吧" action={<Button type="primary" onClick={() => navigate(ROUTES.products)}>去购物</Button>} />
      ) : (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          {orders.map((order) => (
            <div key={order.id} style={{ border: '1px solid var(--color-border)', borderRadius: 8, padding: 16, background: '#fff' }}>
              <Space style={{ width: '100%', justifyContent: 'space-between' }} wrap>
                <Space>
                  <Typography.Text strong>{order.order_no}</Typography.Text>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {formatDateTime(order.created_at)}
                  </Typography.Text>
                </Space>
                <StatusTag kind="order" value={order.status} />
              </Space>
              <Descriptions size="small" column={3} style={{ marginTop: 8 }}>
                <Descriptions.Item label="实付"><MoneyText value={order.paid_amount ?? order.payable_amount} /></Descriptions.Item>
                <Descriptions.Item label="支付状态"><StatusTag kind="payment" value={order.payment_status} /></Descriptions.Item>
                <Descriptions.Item label="履约"><StatusTag kind="fulfillment" value={order.fulfillment_status} /></Descriptions.Item>
              </Descriptions>
              <Space>
                <Link to={ROUTES.orderDetail(order.order_no)}>查看详情</Link>
                <Link to={ROUTES.orderLogistics(order.order_no)}>物流轨迹</Link>
              </Space>
            </div>
          ))}
          <div style={{ textAlign: 'right' }}>
            <Typography.Text type="secondary">共 {total} 条</Typography.Text>
            <Button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} style={{ marginLeft: 8 }}>上一页</Button>
            <Button disabled={page * pageSize >= total} onClick={() => setPage((p) => p + 1)} style={{ marginLeft: 8 }}>下一页</Button>
          </div>
        </Space>
      )}
    </div>
  );
}
