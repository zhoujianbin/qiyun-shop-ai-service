import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Carousel from 'antd/es/carousel';
import Col from 'antd/es/col';
import Row from 'antd/es/row';
import Space from 'antd/es/space';
import Tag from 'antd/es/tag';
import Typography from 'antd/es/typography';
import CustomerServiceOutlined from '@ant-design/icons/CustomerServiceOutlined';
import ExperimentOutlined from '@ant-design/icons/ExperimentOutlined';
import SafetyCertificateOutlined from '@ant-design/icons/SafetyCertificateOutlined';
import ToolOutlined from '@ant-design/icons/ToolOutlined';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { productsApi } from '@/api/endpoints/products';
import { queryKeys } from '@/api/queryKeys';
import { ProductCard } from '@/components/product/ProductCard';
import { EmptyState } from '@/components/common/EmptyState';
import { ErrorState } from '@/components/common/ErrorState';
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton';
import { ROUTES } from '@/constants/routes';
import { PRODUCT_LINES } from '@/types/status';

const BANNERS = [
  {
    title: '栖云智家 · 全屋智能',
    desc: '智能门锁 / 摄像头 / 清洁机器人 / 智能灯具 / 家庭网关',
    image: '/banners/01-whole-home.webp',
    imageSmall: '/banners/01-whole-home-sm.webp',
    scrim: 'linear-gradient(90deg, rgba(17,58,170,.95) 0%, rgba(17,58,170,.72) 45%, rgba(17,58,170,.10) 80%)',
    to: ROUTES.products,
  },
  {
    title: '上门安装与维修',
    desc: '专业服务团队覆盖全国主要城市，安装条件透明可查',
    image: '/banners/02-service.webp',
    imageSmall: '/banners/02-service-sm.webp',
    scrim: 'linear-gradient(90deg, rgba(6,95,120,.95) 0%, rgba(6,95,120,.72) 45%, rgba(6,95,120,.10) 80%)',
    to: ROUTES.products + '?product_line=' + encodeURIComponent('安装维修'),
  },
  {
    title: '配件耗材适配保障',
    desc: '与主商品建立适配关系，买对不买错',
    image: '/banners/03-accessories.webp',
    imageSmall: '/banners/03-accessories-sm.webp',
    scrim: 'linear-gradient(90deg, rgba(6,95,45,.95) 0%, rgba(6,95,45,.72) 45%, rgba(6,95,45,.10) 80%)',
    to: ROUTES.products + '?product_line=' + encodeURIComponent('配件耗材'),
  },
];

/** C 端首页：品牌轮播、产品线入口、热销商品、服务入口。 */
export default function HomePage() {
  const navigate = useNavigate();
  const query = useQuery({
    queryKey: queryKeys.products.list({ status: 'ON_SALE', page: 1, page_size: 8 }),
    queryFn: ({ signal }) => productsApi.publicList({ page: 1, page_size: 8, signal }),
  });

  return (
    <div className="qy-page" style={{ maxWidth: 1200, margin: '0 auto' }}>
      <Carousel autoplay style={{ marginBottom: 24, borderRadius: 12, overflow: 'hidden' }}>
        {BANNERS.map((banner, index) => (
          <div key={banner.title}>
            <div className="qy-banner">
              <img
                className="qy-banner-image"
                src={banner.image}
                srcSet={`${banner.imageSmall} 800w, ${banner.image} 1600w`}
                sizes="(max-width: 768px) 100vw, 1200px"
                alt={banner.title}
                loading={index === 0 ? 'eager' : 'lazy'}
                decoding="async"
              />
              <div className="qy-banner-scrim" style={{ background: banner.scrim }} />
              <div className="qy-banner-body">
                <Typography.Title level={2} style={{ color: '#fff', marginBottom: 8 }}>
                  {banner.title}
                </Typography.Title>
                <Typography.Paragraph style={{ color: 'rgba(255,255,255,.88)', fontSize: 15 }}>{banner.desc}</Typography.Paragraph>
                <Button type="primary" onClick={() => navigate(banner.to)}>立即选购</Button>
              </div>
            </div>
          </div>
        ))}
      </Carousel>

      <Card title="产品线" style={{ marginBottom: 24 }}>
        <Space wrap size={12}>
          {PRODUCT_LINES.map((line) => (
            <Link key={line} to={`${ROUTES.products}?product_line=${encodeURIComponent(line)}`}>
              <Tag color="blue" style={{ padding: '6px 14px', fontSize: 14, cursor: 'pointer' }}>
                {line}
              </Tag>
            </Link>
          ))}
        </Space>
      </Card>

      <Card
        title="热销商品"
        extra={<Link to={ROUTES.products}>查看全部</Link>}
        style={{ marginBottom: 24 }}
      >
        {query.isLoading ? (
          <LoadingSkeleton rows={4} />
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => void query.refetch()} />
        ) : (query.data?.items.length ?? 0) === 0 ? (
          <EmptyState title="暂无在售商品" description="请稍后再来或调整渠道范围" />
        ) : (
          <Row gutter={[16, 16]}>
            {query.data?.items.slice(0, 8).map((product) => (
              <Col key={product.id} xs={12} sm={12} md={8} lg={6}>
                <ProductCard product={product} />
              </Col>
            ))}
          </Row>
        )}
      </Card>

      <Row gutter={[16, 16]}>
        {[
          { icon: <SafetyCertificateOutlined />, title: '正品保障', desc: '官方商城与授权渠道同源供货' },
          { icon: <ToolOutlined />, title: '上门安装', desc: '门锁/摄像头/网关支持预约安装' },
          { icon: <CustomerServiceOutlined />, title: '售后无忧', desc: '在线申请退换修，进度全程可查' },
          { icon: <ExperimentOutlined />, title: '配件适配', desc: '配件耗材与主商品适配关系透明' },
        ].map((item) => (
          <Col key={item.title} xs={12} md={6}>
            <Card>
              <Space direction="vertical" size={4}>
                <span style={{ fontSize: 22, color: '#1F5EFF' }}>{item.icon}</span>
                <Typography.Text strong>{item.title}</Typography.Text>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {item.desc}
                </Typography.Text>
              </Space>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}
