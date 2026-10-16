import Alert from 'antd/es/alert';
import App from 'antd/es/app';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Col from 'antd/es/col';
import Descriptions from 'antd/es/descriptions';
import Divider from 'antd/es/divider';
import Input from 'antd/es/input';
import Modal from 'antd/es/modal';
import Popconfirm from 'antd/es/popconfirm';
import Radio from 'antd/es/radio';
import Row from 'antd/es/row';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Table from 'antd/es/table';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ordersApi } from '@/api/endpoints/orders';
import { paymentsApi } from '@/api/endpoints/payments';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { PageHeader } from '@/components/common/PageHeader';
import { ErrorState } from '@/components/common/ErrorState';
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton';
import { MoneyText } from '@/components/common/MoneyText';
import { StatusTag } from '@/components/common/StatusTag';
import { OrderTimeline } from '@/components/order/OrderTimeline';
import { MaskedText } from '@/components/common/MaskedText';
import { useOrderByNo } from '@/hooks/useOrderByNo';
import { usePermission } from '@/hooks/usePermission';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { errorMessage } from '@/api/errors';
import { formatDateTime } from '@/utils/datetime';
import { CANCEL_REASONS } from '@/constants/orderStatus';
import { PAYMENT_METHOD_OPTIONS } from '@/constants/paymentStatus';
import { ROUTES } from '@/constants/routes';
import type { OrderItem, PaymentMethod } from '@/types/domain';

const CANCELABLE = ['CREATED', 'PENDING_PAYMENT'];

/** C 端订单详情：状态步骤、商品、金额、时间线，以及取消/支付/确认收货/申请售后。 */
export default function OrderDetailPage() {
  const { orderNo } = useParams();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState('CUSTOMER_REQUEST');
  const [cancelNote, setCancelNote] = useState('');
  const [payOpen, setPayOpen] = useState(false);
  const [payMethod, setPayMethod] = useState<PaymentMethod>('MOCK');

  const orderQuery = useOrderByNo(orderNo);
  const order = orderQuery.data;

  const timelineQuery = useQuery({
    queryKey: queryKeys.orders.timeline(order?.id ?? ''),
    queryFn: ({ signal }) => ordersApi.timeline(order!.id, { signal }),
    enabled: Boolean(order?.id),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['orders'] });

  const cancelMutation = useIdempotentMutation(
    (vars: { id: number; reason: string }) => ordersApi.cancel(vars.id, { reason: vars.reason, notify_customer: true }),
    {
      onSuccess: async () => {
        message.success('订单已取消');
        setCancelOpen(false);
        cancelMutation.resetKey();
        await invalidate();
      },
      onError: (error) => message.error(errorMessage(error)),
    },
  );

  const confirmMutation = useIdempotentMutation(
    (id: number) => ordersApi.confirmReceipt(id),
    {
      onSuccess: async () => {
        message.success('已确认收货');
        confirmMutation.resetKey();
        await invalidate();
      },
      onError: (error) => message.error(errorMessage(error)),
    },
  );

  const payMutation = useIdempotentMutation(
    (vars: { orderId: number; method: PaymentMethod }) => paymentsApi.create({ order_id: vars.orderId, method: vars.method }),
    {
      onSuccess: async (payment) => {
        try {
          if (payment.method === 'MOCK') {
            await paymentsApi.mockSucceed(payment.id, {});
            message.success('支付成功（模拟）');
          } else if (payment.pay_url) {
            message.info('请在收银台完成支付');
            window.open(payment.pay_url, '_blank');
          }
          setPayOpen(false);
          payMutation.resetKey();
          await invalidate();
        } catch (error) {
          message.error(errorMessage(error));
        }
      },
      onError: (error) => message.error(errorMessage(error)),
    },
  );

  if (orderQuery.isLoading) {
    return <div className="qy-page"><LoadingSkeleton rows={8} /></div>;
  }
  if (orderQuery.isError || !order) {
    return (
      <div className="qy-page">
        <ErrorState title="订单加载失败" error={orderQuery.error} onRetry={() => void orderQuery.refetch()} />
      </div>
    );
  }

  const canCancel = CANCELABLE.includes(order.status);
  const canConfirm = order.status === 'SHIPPED';
  const canPay = ['UNPAID', 'PARTIAL'].includes(order.payment_status) && ['CREATED', 'PENDING_PAYMENT'].includes(order.status);
  const canApplyAfterSales = ['SHIPPED', 'COMPLETED'].includes(order.status) && order.after_sales_status === 'NONE';

  const columns: ColumnsType<OrderItem> = [
    { title: '商品', dataIndex: 'product_name', key: 'product_name' },
    { title: '规格', dataIndex: 'sku_name', key: 'sku_name' },
    { title: '单价', dataIndex: 'unit_price', key: 'unit_price', render: (v: string) => <MoneyText value={v} /> },
    { title: '数量', dataIndex: 'quantity', key: 'quantity' },
    { title: '应付', dataIndex: 'payable_amount', key: 'payable_amount', render: (v: string) => <MoneyText value={v} /> },
    { title: '售后', dataIndex: 'after_sales_status', key: 'after_sales_status', render: (v: string) => <StatusTag kind="orderAfterSales" value={v} /> },
  ];

  return (
    <div className="qy-page" style={{ maxWidth: 1100, margin: '0 auto' }}>
      <PageHeader
        title={`订单 ${order.order_no}`}
        subtitle={formatDateTime(order.created_at)}
        breadcrumb={[{ label: '我的订单', to: ROUTES.orders }, { label: order.order_no }]}
        tags={<StatusTag kind="order" value={order.status} />}
        extra={
          <Space wrap>
            {canPay ? <Button type="primary" onClick={() => setPayOpen(true)}>去支付</Button> : null}
            {canConfirm ? (
              <Popconfirm title="确认已收到商品？" onConfirm={() => order && confirmMutation.mutate(order.id)} okText="确认收货" cancelText="取消">
                <Button loading={confirmMutation.isPending}>确认收货</Button>
              </Popconfirm>
            ) : null}
            {canCancel ? <Button danger onClick={() => setCancelOpen(true)}>取消订单</Button> : null}
            {canApplyAfterSales ? (
              <Button onClick={() => navigate(`${ROUTES.afterSalesApply}?order_id=${order.id}`)}>申请售后</Button>
            ) : null}
            <Button onClick={() => navigate(ROUTES.orderLogistics(order.order_no))}>物流轨迹</Button>
          </Space>
        }
      />
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card title="商品明细" style={{ marginBottom: 16 }}>
            <Table<OrderItem> rowKey="id" size="small" columns={columns} dataSource={order.items ?? []} pagination={false} />
          </Card>
          <Card title="金额与支付" style={{ marginBottom: 16 }}>
            <Descriptions column={2} size="small">
              <Descriptions.Item label="商品金额"><MoneyText value={order.goods_amount} /></Descriptions.Item>
              <Descriptions.Item label="优惠金额"><MoneyText value={order.discount_amount} /></Descriptions.Item>
              <Descriptions.Item label="运费"><MoneyText value={order.shipping_amount} /></Descriptions.Item>
              <Descriptions.Item label="应付金额"><MoneyText value={order.payable_amount} strong /></Descriptions.Item>
              <Descriptions.Item label="实付金额"><MoneyText value={order.paid_amount} /></Descriptions.Item>
              <Descriptions.Item label="已退款"><MoneyText value={order.refunded_amount} /></Descriptions.Item>
              <Descriptions.Item label="支付状态"><StatusTag kind="payment" value={order.payment_status} /></Descriptions.Item>
              <Descriptions.Item label="支付截止">{formatDateTime(order.pay_deadline)}</Descriptions.Item>
            </Descriptions>
          </Card>
          <Card title="收货与履约">
            <Descriptions column={2} size="small">
              <Descriptions.Item label="收件人">{order.receiver_name ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="联系电话"><MaskedText value={order.receiver_phone_masked} /></Descriptions.Item>
              <Descriptions.Item label="履约状态"><StatusTag kind="fulfillment" value={order.fulfillment_status} /></Descriptions.Item>
              <Descriptions.Item label="发货时间">{formatDateTime(order.shipped_at)}</Descriptions.Item>
              <Descriptions.Item label="买家备注">{order.buyer_remark ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="取消原因">{order.cancel_reason ?? '-'}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="订单时间线">
            <OrderTimeline
              events={timelineQuery.data?.items ?? []}
              loading={timelineQuery.isLoading}
              error={timelineQuery.error}
              onRetry={() => void timelineQuery.refetch()}
            />
          </Card>
        </Col>
      </Row>

      <Modal
        open={cancelOpen}
        title="取消订单"
        okText="确认取消"
        cancelText="再想想"
        okButtonProps={{ danger: true, loading: cancelMutation.isPending }}
        onCancel={() => setCancelOpen(false)}
        onOk={() => {
          if (!order) return;
          if (cancelReason === 'OTHER' && cancelNote.trim().length === 0) {
            message.error('请填写取消原因');
            return;
          }
          cancelMutation.mutate({ id: order.id, reason: cancelReason === 'OTHER' ? cancelNote.trim() : cancelReason });
        }}
        maskClosable={false}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Alert type="warning" showIcon message="取消后订单不可恢复" description="已支付金额将在 1–3 个工作日原路退回。" />
          <Select
            value={cancelReason}
            style={{ width: '100%' }}
            options={CANCEL_REASONS}
            onChange={setCancelReason}
          />
          {cancelReason === 'OTHER' ? (
            <Input.TextArea rows={3} maxLength={200} showCount value={cancelNote} onChange={(event) => setCancelNote(event.target.value)} placeholder="请补充取消原因（≤200 字）" />
          ) : null}
        </Space>
      </Modal>

      <Modal
        open={payOpen}
        title="订单支付"
        okText="创建支付单"
        cancelText="取消"
        confirmLoading={payMutation.isPending}
        onCancel={() => setPayOpen(false)}
        onOk={() => order && payMutation.mutate({ orderId: order.id, method: payMethod })}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Typography.Text>应付金额：<MoneyText value={order.payable_amount} strong /></Typography.Text>
          <Radio.Group value={payMethod} onChange={(event) => setPayMethod(event.target.value as PaymentMethod)}>
            <Space direction="vertical">
              {PAYMENT_METHOD_OPTIONS.map((option) => (
                <Radio key={option.value} value={option.value}>{option.label}</Radio>
              ))}
            </Space>
          </Radio.Group>
          <Divider style={{ margin: '8px 0' }} />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            一期接入模拟支付通道；选择 MOCK 将直接置为支付成功，用于联调。
          </Typography.Text>
        </Space>
      </Modal>
    </div>
  );
}
