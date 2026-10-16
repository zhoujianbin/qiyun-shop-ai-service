import App from 'antd/es/app';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Col from 'antd/es/col';
import Descriptions from 'antd/es/descriptions';
import Divider from 'antd/es/divider';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import Modal from 'antd/es/modal';
import Row from 'antd/es/row';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Switch from 'antd/es/switch';
import Table from 'antd/es/table';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ordersApi } from '@/api/endpoints/orders';
import { refundsApi } from '@/api/endpoints/refunds';
import { shipmentsApi } from '@/api/endpoints/shipments';
import { warehousesApi } from '@/api/endpoints/warehouses';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { PageHeader } from '@/components/common/PageHeader';
import { ErrorState } from '@/components/common/ErrorState';
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton';
import { MoneyText } from '@/components/common/MoneyText';
import { StatusTag } from '@/components/common/StatusTag';
import { OrderTimeline } from '@/components/order/OrderTimeline';
import { ShipDialog } from '@/components/order/ShipDialog';
import { AddressForm } from '@/components/form/AddressForm';
import { PermissionGate } from '@/components/common/PermissionGate';
import { useOrderByNo } from '@/hooks/useOrderByNo';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { errorMessage } from '@/api/errors';
import { formatDateTime } from '@/utils/datetime';
import { canOrderAction } from '@/utils/orderActions';
import { CANCEL_REASONS } from '@/constants/orderStatus';
import { P } from '@/types/permissions';
import { ROUTES } from '@/constants/routes';
import type { OrderAddressUpdateRequest, OrderItem, ShipRequest } from '@/types/domain';

/** B 端订单详情：状态、明细、时间线、发货/取消/改地址/备注/退款/开票。 */
export default function OrderDetailPage() {
  const { orderNo } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [shipOpen, setShipOpen] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState('CUSTOMER_REQUEST');
  const [cancelNote, setCancelNote] = useState('');
  const [remarkOpen, setRemarkOpen] = useState(false);
  const [addressOpen, setAddressOpen] = useState(false);
  const [refundOpen, setRefundOpen] = useState(false);
  const [refundAmount, setRefundAmount] = useState('');
  const [refundReason, setRefundReason] = useState('客户申请退款');
  const [remarkForm] = Form.useForm<{ buyer_remark?: string; staff_remark?: string }>();
  const [addressForm] = Form.useForm<OrderAddressUpdateRequest>();

  const orderQuery = useOrderByNo(orderNo);
  const order = orderQuery.data;

  const timelineQuery = useQuery({
    queryKey: queryKeys.orders.timeline(order?.id ?? ''),
    queryFn: ({ signal }) => ordersApi.timeline(order!.id, { signal }),
    enabled: Boolean(order?.id),
  });
  const warehouseQuery = useQuery({
    queryKey: queryKeys.warehouses.list({ page: 1, page_size: 100 }),
    queryFn: ({ signal }) => warehousesApi.list({ page: 1, page_size: 100, signal }),
  });
  const carrierQuery = useQuery({
    queryKey: queryKeys.carriers.list(),
    queryFn: ({ signal }) => shipmentsApi.carriers({ signal }),
  });

  useEffect(() => {
    if (params.get('action') === 'ship' && order && canOrderAction(order, 'ship')) setShipOpen(true);
  }, [params, order]);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['orders'] });

  const shipMutation = useIdempotentMutation((vars: { id: number; body: ShipRequest }) => ordersApi.ship(vars.id, vars.body), {
    onSuccess: async () => { message.success('发货成功'); setShipOpen(false); shipMutation.resetKey(); await invalidate(); },
    onError: (error) => message.error(errorMessage(error)),
  });

  const cancelMutation = useIdempotentMutation((vars: { id: number; reason: string }) => ordersApi.cancel(vars.id, { reason: vars.reason, notify_customer: true }), {
    onSuccess: async () => { message.success('订单已取消'); setCancelOpen(false); cancelMutation.resetKey(); await invalidate(); },
    onError: (error) => message.error(errorMessage(error)),
  });

  const remarkMutation = useIdempotentMutation((vars: { id: number; buyer?: string | null; staff?: string | null }) => ordersApi.updateRemark(vars.id, { buyer_remark: vars.buyer ?? null, staff_remark: vars.staff ?? null }), {
    onSuccess: async () => { message.success('备注已更新'); setRemarkOpen(false); remarkMutation.resetKey(); await invalidate(); },
    onError: (error) => message.error(errorMessage(error)),
  });

  const addressMutation = useIdempotentMutation((vars: { id: number; body: OrderAddressUpdateRequest }) => ordersApi.updateAddress(vars.id, vars.body), {
    onSuccess: async () => { message.success('收货地址已更新'); setAddressOpen(false); addressMutation.resetKey(); await invalidate(); },
    onError: (error) => message.error(errorMessage(error)),
  });

  const refundMutation = useIdempotentMutation((vars: { orderId: number; amount?: string; reason: string }) => refundsApi.create({ order_id: vars.orderId, amount: vars.amount ?? null, reason: vars.reason }), {
    onSuccess: async () => { message.success('退款单已创建，待审核执行'); setRefundOpen(false); refundMutation.resetKey(); await queryClient.invalidateQueries({ queryKey: ['refunds'] }); navigate(ROUTES.adminRefunds); },
    onError: (error) => message.error(errorMessage(error)),
  });

  if (orderQuery.isLoading) return <div className="qy-page"><LoadingSkeleton rows={10} /></div>;
  if (orderQuery.isError || !order) {
    return <div className="qy-page"><ErrorState title="订单加载失败或不存在" error={orderQuery.error} onRetry={() => void orderQuery.refetch()} /></div>;
  }

  const itemColumns: ColumnsType<OrderItem> = [
    { title: '商品', dataIndex: 'product_name', key: 'product_name' },
    { title: '规格', dataIndex: 'sku_name', key: 'sku_name' },
    { title: '单价', dataIndex: 'unit_price', key: 'unit_price', render: (value: string) => <MoneyText value={value} /> },
    { title: '数量', dataIndex: 'quantity', key: 'quantity' },
    { title: '已发', dataIndex: 'shipped_quantity', key: 'shipped_quantity', render: (value?: number) => value ?? 0 },
    { title: '应付', dataIndex: 'payable_amount', key: 'payable_amount', render: (value: string) => <MoneyText value={value} /> },
    { title: '售后', dataIndex: 'after_sales_status', key: 'after_sales_status', render: (value: string) => <StatusTag kind="orderAfterSales" value={value} /> },
  ];

  return (
    <div className="qy-page">
      <PageHeader
        title={`订单 ${order.order_no}`}
        subtitle={`下单时间 ${formatDateTime(order.created_at)} · 版本 ${order.version ?? '-'}`}
        breadcrumb={[{ label: '订单管理', to: ROUTES.adminOrders }, { label: order.order_no }]}
        tags={
          <Space size={4} wrap>
            <StatusTag kind="order" value={order.status} />
            <StatusTag kind="payment" value={order.payment_status} />
            <StatusTag kind="fulfillment" value={order.fulfillment_status} />
            <StatusTag kind="orderAfterSales" value={order.after_sales_status} />
          </Space>
        }
        extra={
          <Space wrap>
            {canOrderAction(order, 'ship') ? (
              <PermissionGate permission={P.fulfillmentWrite} mode="disable" fallbackReason="需要履约写权限">
                <Button type="primary" onClick={() => setShipOpen(true)}>发货</Button>
              </PermissionGate>
            ) : null}
            {canOrderAction(order, 'editAddress') ? (
              <PermissionGate permission={P.orderWrite} mode="disable" fallbackReason="需要订单写权限">
                <Button onClick={() => {
                  addressForm.setFieldsValue({
                    receiver_name: order.receiver_name,
                    receiver_mobile: '',
                    province: String((order.shipping_address as Record<string, unknown> | undefined)?.province ?? ''),
                    city: String((order.shipping_address as Record<string, unknown> | undefined)?.city ?? ''),
                    district: String((order.shipping_address as Record<string, unknown> | undefined)?.district ?? ''),
                    detail: String((order.shipping_address as Record<string, unknown> | undefined)?.detail ?? ''),
                  });
                  setAddressOpen(true);
                }}>改地址</Button>
              </PermissionGate>
            ) : null}
            {canOrderAction(order, 'editRemark') ? (
              <PermissionGate permission={P.orderWrite} mode="disable" fallbackReason="需要订单写权限">
                <Button onClick={() => { remarkForm.setFieldsValue({ buyer_remark: order.buyer_remark ?? undefined, staff_remark: order.staff_remark ?? undefined }); setRemarkOpen(true); }}>改备注</Button>
              </PermissionGate>
            ) : null}
            {canOrderAction(order, 'refund') ? (
              <PermissionGate permission={P.aftersalesReview} mode="disable" fallbackReason="需要退款审核权限">
                <Button onClick={() => { setRefundAmount(order.paid_amount ?? ''); setRefundOpen(true); }}>发起退款</Button>
              </PermissionGate>
            ) : null}
            {canOrderAction(order, 'invoice') ? (
              <PermissionGate permission={P.invoiceWrite} mode="disable" fallbackReason="需要发票写权限">
                <Button onClick={() => navigate(`${ROUTES.adminInvoices}?order_id=${order.id}`)}>开票</Button>
              </PermissionGate>
            ) : null}
            {canOrderAction(order, 'cancel') ? (
              <PermissionGate permission={P.orderWrite} mode="disable" fallbackReason="需要订单写权限">
                <Button danger onClick={() => setCancelOpen(true)}>取消订单</Button>
              </PermissionGate>
            ) : null}
          </Space>
        }
      />
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card title="商品明细" style={{ marginBottom: 16 }}>
            <Table<OrderItem> rowKey="id" size="small" columns={itemColumns} dataSource={order.items ?? []} pagination={false} />
          </Card>
          <Card title="金额信息" style={{ marginBottom: 16 }}>
            <Descriptions column={3} size="small">
              <Descriptions.Item label="商品金额"><MoneyText value={order.goods_amount} /></Descriptions.Item>
              <Descriptions.Item label="优惠金额"><MoneyText value={order.discount_amount} /></Descriptions.Item>
              <Descriptions.Item label="运费"><MoneyText value={order.shipping_amount} /></Descriptions.Item>
              <Descriptions.Item label="应付"><MoneyText value={order.payable_amount} strong /></Descriptions.Item>
              <Descriptions.Item label="实付"><MoneyText value={order.paid_amount} /></Descriptions.Item>
              <Descriptions.Item label="已退款"><MoneyText value={order.refunded_amount} /></Descriptions.Item>
            </Descriptions>
          </Card>
          <Card title="收货与备注">
            <Descriptions column={2} size="small">
              <Descriptions.Item label="收件人">{order.receiver_name ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="电话">{order.receiver_phone_masked ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="买家备注">{order.buyer_remark ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="商家备注">{order.staff_remark ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="取消原因" span={2}>{order.cancel_reason ?? '-'}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="订单时间线">
            <OrderTimeline events={timelineQuery.data?.items ?? []} loading={timelineQuery.isLoading} error={timelineQuery.error} onRetry={() => void timelineQuery.refetch()} />
          </Card>
        </Col>
      </Row>

      <ShipDialog
        open={shipOpen}
        order={order}
        warehouses={warehouseQuery.data?.items ?? []}
        carriers={carrierQuery.data?.items ?? []}
        loading={shipMutation.isPending}
        onCancel={() => setShipOpen(false)}
        onSubmit={(payload) => order && shipMutation.mutate({ id: order.id, body: payload })}
      />

      <Modal
        open={cancelOpen}
        title="取消订单"
        okText="确认取消"
        cancelText="返回"
        okButtonProps={{ danger: true, loading: cancelMutation.isPending }}
        onCancel={() => setCancelOpen(false)}
        onOk={() => {
          if (cancelReason === 'OTHER' && cancelNote.trim().length === 0) { message.error('请填写取消原因'); return; }
          cancelMutation.mutate({ id: order.id, reason: cancelReason === 'OTHER' ? cancelNote.trim() : cancelReason });
        }}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Typography.Text type="warning">取消不可逆；已支付订单将进入退款流程。</Typography.Text>
          <Select value={cancelReason} style={{ width: '100%' }} options={CANCEL_REASONS} onChange={setCancelReason} />
          {cancelReason === 'OTHER' ? <Input.TextArea rows={3} maxLength={200} showCount value={cancelNote} onChange={(event) => setCancelNote(event.target.value)} placeholder="补充取消原因" /> : null}
          <Switch defaultChecked disabled /> <Typography.Text type="secondary">通知客户</Typography.Text>
        </Space>
      </Modal>

      <Modal open={remarkOpen} title="修改备注" okText="保存" cancelText="取消" confirmLoading={remarkMutation.isPending} onCancel={() => setRemarkOpen(false)} onOk={() => { void remarkForm.validateFields().then((values) => remarkMutation.mutate({ id: order.id, buyer: values.buyer_remark, staff: values.staff_remark })); }} destroyOnClose>
        <Form form={remarkForm} layout="vertical">
          <Form.Item label="买家备注" name="buyer_remark"><Input.TextArea rows={2} maxLength={200} showCount /></Form.Item>
          <Form.Item label="商家备注" name="staff_remark"><Input.TextArea rows={2} maxLength={200} showCount /></Form.Item>
        </Form>
      </Modal>

      <Modal open={addressOpen} title="修改收货地址" okText="保存" cancelText="取消" width={640} confirmLoading={addressMutation.isPending} onCancel={() => setAddressOpen(false)} onOk={() => { void addressForm.validateFields().then((values) => addressMutation.mutate({ id: order.id, body: values })); }} destroyOnClose>
        <Typography.Text type="secondary">发货后地址不可修改；仅支持在未发货状态变更。</Typography.Text>
        <Divider />
        <AddressForm form={addressForm} />
      </Modal>

      <Modal open={refundOpen} title="发起退款" okText="创建退款单" cancelText="取消" confirmLoading={refundMutation.isPending} onCancel={() => setRefundOpen(false)} onOk={() => refundMutation.mutate({ orderId: order.id, amount: refundAmount || undefined, reason: refundReason })}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Typography.Text>可退金额上限：<MoneyText value={order.paid_amount} strong /></Typography.Text>
          <Input value={refundAmount} onChange={(event) => setRefundAmount(event.target.value)} placeholder="退款金额，留空为全额" />
          <Input.TextArea rows={2} maxLength={200} value={refundReason} onChange={(event) => setRefundReason(event.target.value)} placeholder="退款原因" />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>创建后需在“退款审核”执行退款，退款不可逆。</Typography.Text>
        </Space>
      </Modal>
    </div>
  );
}
