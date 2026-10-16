import App from 'antd/es/app';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Col from 'antd/es/col';
import Descriptions from 'antd/es/descriptions';
import Divider from 'antd/es/divider';
import Image from 'antd/es/image';
import InputNumber from 'antd/es/input-number';
import Row from 'antd/es/row';
import Space from 'antd/es/space';
import Tag from 'antd/es/tag';
import Typography from 'antd/es/typography';
import ShoppingCartOutlined from '@ant-design/icons/ShoppingCartOutlined';
import ThunderboltOutlined from '@ant-design/icons/ThunderboltOutlined';
import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { productsApi } from '@/api/endpoints/products';
import { queryKeys } from '@/api/queryKeys';
import { cartApi } from '@/api/endpoints/cart';
import { ErrorState } from '@/components/common/ErrorState';
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton';
import { MoneyText } from '@/components/common/MoneyText';
import { PageHeader } from '@/components/common/PageHeader';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { useAuthStore } from '@/stores/authStore';
import { queryClient } from '@/app/providers';
import { errorMessage } from '@/api/errors';
import { ROUTES } from '@/constants/routes';

/** C 端商品详情：SKU 选择、价格、适配与安装服务说明。 */
export default function ProductDetailPage() {
  const { productId } = useParams();
  const id = Number(productId);
  const navigate = useNavigate();
  const { message } = App.useApp();
  const user = useAuthStore((state) => state.user);
  const [skuId, setSkuId] = useState<number | null>(null);
  const [quantity, setQuantity] = useState(1);

  const query = useQuery({
    queryKey: queryKeys.products.publicDetail(id),
    queryFn: ({ signal }) => productsApi.publicDetail(id),
    enabled: Number.isFinite(id),
  });

  const product = query.data;
  const skus = product?.skus ?? [];
  const currentSku = useMemo(() => skus.find((sku) => sku.id === skuId) ?? skus.find((sku) => sku.status === 'ON_SALE') ?? null, [skus, skuId]);

  const addToCart = useIdempotentMutation(
    (vars: { skuId: number; quantity: number }) => cartApi.addItem({ sku_id: vars.skuId, quantity: vars.quantity }),
    {
      onSuccess: () => {
        message.success('已加入购物车');
        void queryClient.invalidateQueries({ queryKey: ['cart'] });
      },
      onError: (error) => message.error(errorMessage(error)),
    },
  );

  if (query.isLoading) {
    return (
      <div className="qy-page" style={{ maxWidth: 1200, margin: '0 auto' }}>
        <LoadingSkeleton rows={10} />
      </div>
    );
  }
  if (query.isError || !product) {
    return (
      <div className="qy-page" style={{ maxWidth: 1200, margin: '0 auto' }}>
        <ErrorState title="商品加载失败" error={query.error} onRetry={() => void query.refetch()} />
      </div>
    );
  }

  const inStock = currentSku?.status === 'ON_SALE';
  const requireLogin = () => {
    if (!user) {
      navigate(`${ROUTES.login}?redirect=${encodeURIComponent(`/products/${id}`)}`);
      return true;
    }
    return false;
  };

  const handleAddCart = () => {
    if (requireLogin()) return;
    if (!currentSku) {
      message.warning('请先选择规格');
      return;
    }
    addToCart.mutate({ skuId: currentSku.id, quantity });
  };

  const handleBuyNow = () => {
    if (requireLogin()) return;
    if (!currentSku) {
      message.warning('请先选择规格');
      return;
    }
    navigate(`${ROUTES.checkout}?source=BUY_NOW&sku_id=${currentSku.id}&quantity=${quantity}`);
  };

  return (
    <div className="qy-page" style={{ maxWidth: 1200, margin: '0 auto' }}>
      <PageHeader title={product.name} subtitle={product.subtitle ?? undefined} breadcrumb={[{ label: '首页', to: ROUTES.home }, { label: '商品', to: ROUTES.products }, { label: product.name }]} />
      <Row gutter={[24, 24]}>
        <Col xs={24} md={10}>
          <Image.PreviewGroup>
            <Image
              src={product.media?.find((item) => item.is_main)?.url ?? product.media?.[0]?.url}
              fallback="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0MDAiIGhlaWdodD0iNDAwIj48cmVjdCB3aWR0aD0iNDAwIiBoZWlnaHQ9IjQwMCIgZmlsbD0iI0VFRjNGRiIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmaWxsPSIjOTRhM2I4IiBmb250LXNpemU9IjE2IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIj7llYblk4Hlm77niYc8L3RleHQ+PC9zdmc+"
              style={{ width: '100%', borderRadius: 8 }}
            />
            <Space style={{ marginTop: 8 }} wrap>
              {(product.media ?? []).slice(1, 6).map((item) => (
                <Image key={item.id ?? item.url} src={item.url} width={64} height={64} style={{ objectFit: 'cover', borderRadius: 6 }} />
              ))}
            </Space>
          </Image.PreviewGroup>
        </Col>
        <Col xs={24} md={14}>
          <Card>
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <div>
                <MoneyText value={currentSku?.price ?? product.min_price} strong style={{ fontSize: 26 }} />
                {currentSku?.market_price ? (
                  <Typography.Text delete type="secondary" style={{ marginLeft: 8 }}>
                    <MoneyText value={currentSku.market_price} />
                  </Typography.Text>
                ) : null}
              </div>
              <Space wrap>
                {product.category_name ? <Tag>{product.category_name}</Tag> : null}
                {product.brand_name ? <Tag color="blue">{product.brand_name}</Tag> : null}
              </Space>
              <div>
                <Typography.Text type="secondary">选择规格</Typography.Text>
                <div style={{ marginTop: 8 }}>
                  <Space wrap>
                    {skus.map((sku) => (
                      <Button
                        key={sku.id}
                        type={currentSku?.id === sku.id ? 'primary' : 'default'}
                        disabled={sku.status !== 'ON_SALE'}
                        onClick={() => setSkuId(sku.id)}
                      >
                        {sku.name}
                        {sku.status !== 'ON_SALE' ? '（缺货）' : ''}
                      </Button>
                    ))}
                    {skus.length === 0 ? <Typography.Text type="secondary">暂无 SKU</Typography.Text> : null}
                  </Space>
                </div>
              </div>
              <Space>
                <Typography.Text type="secondary">数量</Typography.Text>
                <InputNumber min={1} max={999} value={quantity} onChange={(value) => setQuantity(Number(value ?? 1))} />
              </Space>
              <Space>
                <Button type="primary" icon={<ShoppingCartOutlined />} loading={addToCart.isPending} disabled={!inStock} onClick={handleAddCart}>
                  加入购物车
                </Button>
                <Button icon={<ThunderboltOutlined />} disabled={!inStock} onClick={handleBuyNow}>
                  立即购买
                </Button>
                {!inStock ? <Typography.Text type="danger">当前规格缺货</Typography.Text> : null}
              </Space>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                价格以最新接口为准；未选择规格无法加购。
              </Typography.Text>
            </Space>
          </Card>
        </Col>
      </Row>

      <Divider />
      <Row gutter={[16, 16]}>
        <Col xs={24} md={12}>
          <Card title="规格与属性">
            <Descriptions column={1} size="small">
              {(product.attributes ?? []).map((attr) => (
                <Descriptions.Item key={attr.code} label={attr.name}>
                  {attr.value_text}
                  {attr.unit ? ` ${attr.unit}` : ''}
                </Descriptions.Item>
              ))}
              {Object.entries(product.spec_summary ?? {}).map(([key, value]) => (
                <Descriptions.Item key={key} label={key}>
                  {String(value)}
                </Descriptions.Item>
              ))}
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="服务与保修">
            <Space direction="vertical" size={8}>
              <Typography.Text>保修摘要：{product.warranty_summary ?? '以随箱保修卡为准'}</Typography.Text>
              <Typography.Text>
                安装服务：{product.install_required ? '需上门安装' : '无需上门安装'}
              </Typography.Text>
              {product.install_notes ? <Typography.Text>安装条件：{product.install_notes}</Typography.Text> : null}
              {product.service_scope ? <Typography.Text>服务范围：{product.service_scope}</Typography.Text> : null}
            </Space>
          </Card>
        </Col>
      </Row>
      {product.description_md ? (
        <Card title="商品详情" style={{ marginTop: 16 }}>
          <Typography.Paragraph style={{ whiteSpace: 'pre-wrap' }}>{product.description_md}</Typography.Paragraph>
        </Card>
      ) : null}
    </div>
  );
}
