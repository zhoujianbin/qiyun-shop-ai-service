import App from 'antd/es/app';
import Alert from 'antd/es/alert';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Checkbox from 'antd/es/checkbox';
import Col from 'antd/es/col';
import Divider from 'antd/es/divider';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import Radio from 'antd/es/radio';
import Row from 'antd/es/row';
import Space from 'antd/es/space';
import Typography from 'antd/es/typography';
import { useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { cartApi } from '@/api/endpoints/cart';
import { customersApi } from '@/api/endpoints/customers';
import { ordersApi } from '@/api/endpoints/orders';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { PageHeader } from '@/components/common/PageHeader';
import { EmptyState } from '@/components/common/EmptyState';
import { ErrorState } from '@/components/common/ErrorState';
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton';
import { MoneyText } from '@/components/common/MoneyText';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { useAuthStore } from '@/stores/authStore';
import { errorMessage } from '@/api/errors';
import { toCents, formatMoney } from '@/utils/money';
import { ROUTES } from '@/constants/routes';
import type { CreateOrderRequest } from '@/types/domain';

const DEFAULT_CHANNEL_ID = 1;

/** C 端结算：地址、备注、金额明细；提交按钮防重复，幂等键复用。 */
export default function CheckoutPage() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const user = useAuthStore((state) => state.user);
  const customerId = user?.id;
  const source = params.get('source') === 'BUY_NOW' ? 'BUY_NOW' : 'CART';
  const skuId = Number(params.get('sku_id') ?? 0);
  const quantity = Number(params.get('quantity') ?? 1);

  const [addressId, setAddressId] = useState<number | null>(null);
  const [buyerRemark, setBuyerRemark] = useState('');
  const [agree, setAgree] = useState(true);

  const cartQuery = useQuery({
    queryKey: queryKeys.cart.detail({ checkout: true }),
    queryFn: ({ signal }) => cartApi.get({ signal }),
    enabled: source === 'CART',
  });

  const addressQuery = useQuery({
    queryKey: queryKeys.customers.addresses(customerId ?? 0),
    queryFn: ({ signal }) => customersApi.myAddresses(),
    enabled: Boolean(customerId),
  });

  const selectedItems = (cartQuery.data?.items ?? []).filter((item) => item.selected);
  const goodsAmount = selectedItems.reduce((sum, item) => sum + toCents(item.unit_price) * (item.quantity ?? 0), 0);

  const address = useMemo(() => {
    const list = addressQuery.data ?? [];
    return list.find((item) => item.id === addressId) ?? list.find((item) => item.is_default) ?? list[0] ?? null;
  }, [addressQuery.data, addressId]);

  const createOrder = useIdempotentMutation(
    (vars: CreateOrderRequest) => ordersApi.create(vars),
    {
      onSuccess: async (order) => {
        message.success('下单成功');
        await queryClient.invalidateQueries({ queryKey: ['orders'] });
        await queryClient.invalidateQueries({ queryKey: ['cart'] });
        createOrder.resetKey();
        navigate(ROUTES.orderDetail(order.order_no));
      },
      onError: (error) => message.error(errorMessage(error)),
    },
  );

  const submit = async () => {
    if (!address) {
      message.error('请先选择收货地址');
      return;
    }
    if (!agree) {
      message.error('请阅读并同意购买协议');
      return;
    }
    if (source === 'CART' && selectedItems.length === 0) {
      message.error('请先在购物车勾选商品');
      return;
    }
    const channelAccountId = cartQuery.data?.channel_account_id ?? DEFAULT_CHANNEL_ID;
    const payload: CreateOrderRequest = {
      channel_account_id: channelAccountId,
      source_mode: source,
      address_id: address.id,
      buyer_remark: buyerRemark || null,
      ...(source === 'CART'
        ? { cart_item_ids: selectedItems.map((item) => item.id) }
        : { items: [{ sku_id: skuId, quantity }] }),
    };
    createOrder.mutate(payload);
  };

  return (
    <div className="qy-page" style={{ maxWidth: 1100, margin: '0 auto' }}>
      <PageHeader title="结算下单" breadcrumb={[{ label: '购物车', to: ROUTES.cart }, { label: '结算' }]} />
      {cartQuery.isError || addressQuery.isError ? (
        <ErrorState error={cartQuery.error ?? addressQuery.error} onRetry={() => { void cartQuery.refetch(); void addressQuery.refetch(); }} />
      ) : (
        <Row gutter={[16, 16]}>
          <Col xs={24} md={15}>
            <Card title="收货地址" style={{ marginBottom: 16 }}>
              {addressQuery.isLoading ? (
                <LoadingSkeleton rows={2} title={false} />
              ) : (addressQuery.data?.length ?? 0) === 0 ? (
                <EmptyState
                  title="还没有收货地址"
                  description="请先新增收货地址再下单"
                  action={<Button type="primary" onClick={() => navigate(ROUTES.addresses)}>新增地址</Button>}
                />
              ) : (
                <Radio.Group value={address?.id} onChange={(event) => setAddressId(event.target.value as number)}>
                  <Space direction="vertical">
                    {(addressQuery.data ?? []).map((item) => (
                      <Radio key={item.id} value={item.id}>
                        <Space direction="vertical" size={0}>
                          <Typography.Text strong>
                            {item.receiver_name} {item.is_default ? <Typography.Text type="success">默认</Typography.Text> : null}
                          </Typography.Text>
                          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                            {item.receiver_mobile_masked} · {item.province}{item.city}{item.district}{item.detail}
                          </Typography.Text>
                        </Space>
                      </Radio>
                    ))}
                  </Space>
                </Radio.Group>
              )}
            </Card>

            <Card title="商品清单">
              {source === 'CART' && cartQuery.isLoading ? (
                <LoadingSkeleton rows={3} />
              ) : source === 'CART' ? (
                selectedItems.length === 0 ? (
                  <EmptyState title="没有勾选商品" action={<Button onClick={() => navigate(ROUTES.cart)}>返回购物车</Button>} />
                ) : (
                  <Space direction="vertical" style={{ width: '100%' }}>
                    {selectedItems.map((item) => (
                      <Row key={item.id} justify="space-between">
                        <Col>
                          <Typography.Text>{item.product_name} · {item.sku_name}</Typography.Text>
                        </Col>
                        <Col>
                          <Typography.Text type="secondary">
                            <MoneyText value={item.unit_price} /> × {item.quantity}
                          </Typography.Text>
                        </Col>
                      </Row>
                    ))}
                  </Space>
                )
              ) : (
                <Typography.Text>SKU #{skuId} × {quantity}</Typography.Text>
              )}
            </Card>

            <Card title="备注" style={{ marginTop: 16 }}>
              <Form layout="vertical">
                <Form.Item label="买家备注">
                  <Input.TextArea rows={2} maxLength={200} showCount value={buyerRemark} onChange={(event) => setBuyerRemark(event.target.value)} placeholder="选填，如安装时间偏好、门锁适配型号" />
                </Form.Item>
              </Form>
            </Card>
          </Col>

          <Col xs={24} md={9}>
            <Card title="金额明细">
              <Space direction="vertical" style={{ width: '100%' }} size={8}>
                <Row justify="space-between">
                  <Col>商品金额</Col>
                  <Col><MoneyText value={formatMoney(String(goodsAmount / 100))} /></Col>
                </Row>
                <Row justify="space-between">
                  <Col>运费</Col>
                  <Col><MoneyText value="0.00" /></Col>
                </Row>
                <Divider style={{ margin: '8px 0' }} />
                <Row justify="space-between">
                  <Col><Typography.Text strong>应付金额</Typography.Text></Col>
                  <Col><MoneyText value={formatMoney(String(goodsAmount / 100))} strong style={{ fontSize: 18 }} /></Col>
                </Row>
                <Alert type="info" showIcon message="提交后将创建订单并锁定库存；请在待付款状态完成支付。" />
                <Checkbox checked={agree} onChange={(event) => setAgree(event.target.checked)}>
                  我已阅读并同意《购买协议》与《售后服务条款》
                </Checkbox>
                <Button type="primary" block size="large" loading={createOrder.isPending} onClick={() => void submit()}>
                  提交订单
                </Button>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  重复提交已通过 Idempotency-Key 防护，不会生成重复订单。
                </Typography.Text>
              </Space>
            </Card>
          </Col>
        </Row>
      )}
    </div>
  );
}
