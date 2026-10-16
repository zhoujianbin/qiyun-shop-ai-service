import Card from 'antd/es/card';
import Col from 'antd/es/col';
import Descriptions from 'antd/es/descriptions';
import Empty from 'antd/es/empty';
import Row from 'antd/es/row';
import Space from 'antd/es/space';
import Timeline from 'antd/es/timeline';
import Typography from 'antd/es/typography';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { shipmentsApi } from '@/api/endpoints/shipments';
import { queryKeys } from '@/api/queryKeys';
import { PageHeader } from '@/components/common/PageHeader';
import { ErrorState } from '@/components/common/ErrorState';
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton';
import { StatusTag } from '@/components/common/StatusTag';
import { MaskedText } from '@/components/common/MaskedText';
import { useOrderByNo } from '@/hooks/useOrderByNo';
import { formatDateTime } from '@/utils/datetime';
import { ROUTES } from '@/constants/routes';

/** C 端物流详情：承运商、运单号与轨迹时间线。 */
export default function LogisticsDetailPage() {
  const { orderNo } = useParams();
  const orderQuery = useOrderByNo(orderNo);
  const order = orderQuery.data;

  const query = useQuery({
    queryKey: queryKeys.shipments.list({ order_id: order?.id }),
    queryFn: ({ signal }) => shipmentsApi.list({ order_id: order?.id, page: 1, page_size: 20, signal }),
    enabled: Boolean(order?.id),
  });

  const shipments = query.data?.items ?? [];

  return (
    <div className="qy-page" style={{ maxWidth: 1000, margin: '0 auto' }}>
      <PageHeader
        title="物流轨迹"
        breadcrumb={[{ label: '我的订单', to: ROUTES.orders }, { label: orderNo ?? '订单' }]}
      />
      {orderQuery.isLoading || query.isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : orderQuery.isError || query.isError ? (
        <ErrorState error={orderQuery.error ?? query.error} onRetry={() => { void orderQuery.refetch(); void query.refetch(); }} />
      ) : shipments.length === 0 ? (
        <Empty description="暂无包裹信息，商家发货后可查看轨迹" />
      ) : (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          {shipments.map((shipment) => (
            <Card key={shipment.id} title={`包裹 ${shipment.shipment_no}`} extra={<StatusTag kind="shipment" value={shipment.status} />}>
              <Row gutter={[16, 16]}>
                <Col xs={24} md={10}>
                  <Descriptions column={1} size="small">
                    <Descriptions.Item label="承运商">{shipment.carrier_name ?? shipment.carrier_code}</Descriptions.Item>
                    <Descriptions.Item label="运单号">{shipment.tracking_no}</Descriptions.Item>
                    <Descriptions.Item label="收件人">{shipment.receiver_name ?? '-'}</Descriptions.Item>
                    <Descriptions.Item label="电话"><MaskedText value={shipment.receiver_phone_masked} /></Descriptions.Item>
                    <Descriptions.Item label="发货时间">{formatDateTime(shipment.shipped_at)}</Descriptions.Item>
                    <Descriptions.Item label="签收时间">{formatDateTime(shipment.delivered_at)}</Descriptions.Item>
                  </Descriptions>
                </Col>
                <Col xs={24} md={14}>
                  {(shipment.tracking_events ?? []).length === 0 ? (
                    <Typography.Text type="secondary">暂无物流轨迹</Typography.Text>
                  ) : (
                    <Timeline
                      items={(shipment.tracking_events ?? []).map((event) => ({
                        children: (
                          <div>
                            <Typography.Text strong>{event.description}</Typography.Text>
                            <div>
                              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                                {formatDateTime(event.event_time)} {event.location ? ` · ${event.location}` : ''}
                              </Typography.Text>
                            </div>
                          </div>
                        ),
                      }))}
                    />
                  )}
                </Col>
              </Row>
            </Card>
          ))}
        </Space>
      )}
    </div>
  );
}
