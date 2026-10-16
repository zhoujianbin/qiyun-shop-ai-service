import Card from 'antd/es/card';
import Space from 'antd/es/space';
import Tag from 'antd/es/tag';
import Typography from 'antd/es/typography';
import { Link } from 'react-router-dom';
import { MoneyText } from '../common/MoneyText';
import { ROUTES } from '@/constants/routes';
import type { Product, ProductPublic } from '@/types/domain';

export interface ProductCardProps {
  product: Product | ProductPublic;
  showStatus?: boolean;
}

/** C 端商品卡：主图、名称、价格区间、卖点。 */
export function ProductCard({ product, showStatus }: ProductCardProps) {
  const minPrice = 'min_price' in product ? product.min_price : undefined;
  const maxPrice = 'max_price' in product ? product.max_price : undefined;
  const media = product.media ?? [];
  const main = media.find((item) => item.is_main) ?? media[0];
  const mainImage = main?.thumb_url ?? main?.url;
  const status = 'status' in product ? product.status : undefined;

  return (
    <Card
      hoverable
      styles={{ body: { padding: 12 } }}
      cover={
        <Link to={ROUTES.productDetail(product.id)} aria-label={product.name}>
          <div
            style={{
              height: 172,
              background: mainImage ? `url(${mainImage}) center/cover no-repeat` : 'linear-gradient(135deg,#EEF3FF,#F5F7FA)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#94a3b8',
              fontSize: 13,
            }}
          >
            {mainImage ? null : '商品图片'}
          </div>
        </Link>
      }
    >
      <Space direction="vertical" size={6} style={{ width: '100%' }}>
        <Link to={ROUTES.productDetail(product.id)}>
          <Typography.Text strong ellipsis style={{ display: 'block' }}>
            {product.name}
          </Typography.Text>
        </Link>
        {product.subtitle ? (
          <Typography.Text type="secondary" ellipsis style={{ fontSize: 12, display: 'block' }}>
            {product.subtitle}
          </Typography.Text>
        ) : null}
        <Space size={6} wrap>
          <MoneyText value={minPrice} strong />
          {maxPrice && maxPrice !== minPrice ? <Typography.Text type="secondary">起</Typography.Text> : null}
          {showStatus && status ? <Tag color={status === 'ON_SALE' ? 'success' : 'default'}>{status === 'ON_SALE' ? '在售' : status}</Tag> : null}
        </Space>
        {product.highlights && product.highlights.length > 0 ? (
          <Space size={4} wrap>
            {product.highlights.slice(0, 2).map((item) => (
              <Tag key={item} color="blue" style={{ marginInlineEnd: 0 }}>
                {item}
              </Tag>
            ))}
          </Space>
        ) : null}
      </Space>
    </Card>
  );
}
