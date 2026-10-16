import Card from 'antd/es/card';
import Col from 'antd/es/col';
import DatePicker from 'antd/es/date-picker';
import Row from 'antd/es/row';
import Space from 'antd/es/space';
import Typography from 'antd/es/typography';
import type { Dayjs } from 'dayjs';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { reportsApi } from '@/api/endpoints/reports';
import { queryKeys } from '@/api/queryKeys';
import { PageHeader } from '@/components/common/PageHeader';
import { StatCard } from '@/components/common/StatCard';
import { ChartCard } from '@/components/charts/ChartCard';
import { BarList } from '@/components/charts/BarList';
import { ChannelScopeSelect } from '@/components/common/ChannelScopeSelect';
import { useChannelScope } from '@/hooks/useChannelScope';
import { usePermission } from '@/hooks/usePermission';
import { formatMoney, toCents } from '@/utils/money';
import { pickNumber, pickString } from '@/utils/report';
import { dayjs } from '@/utils/datetime';
import { P } from '@/types/permissions';

/** B 端工作台：经营指标卡 + 渠道与商品结构；按权限裁剪卡片。 */
export default function DashboardPage() {
  const [range, setRange] = useState<[Dayjs, Dayjs]>([dayjs().subtract(29, 'day'), dayjs()]);
  const { activeChannelId } = useChannelScope();
  const canOrder = usePermission(P.orderRead);
  const canInventory = usePermission(P.inventoryRead);
  const canAfterSales = usePermission(P.aftersalesRead);

  const params = {
    date_from: range[0].format('YYYY-MM-DD'),
    date_to: range[1].format('YYYY-MM-DD'),
    channel_account_id: activeChannelId ?? undefined,
  };

  const query = useQuery({
    queryKey: queryKeys.reports.dashboard(params),
    queryFn: ({ signal }) => reportsApi.dashboard({ ...params, signal }),
    enabled: canOrder,
  });

  const data = query.data;
  const topProducts = (data?.top_products ?? []).map((item) => {
    const record = item as Record<string, unknown>;
    return {
      label: pickString(record, ['product_name', 'name', 'sku_code', 'sku_name'], '商品'),
      value: pickNumber(record, ['amount', 'gmv', 'sales_amount', 'payable_amount']),
      money: true,
    };
  });
  const channels = (data?.channel_breakdown ?? []).map((item) => {
    const record = item as Record<string, unknown>;
    return {
      label: pickString(record, ['channel_name', 'name', 'source', 'channel_type'], '渠道'),
      value: pickNumber(record, ['amount', 'gmv', 'order_count', 'count']),
    };
  });

  return (
    <div className="qy-page">
      <PageHeader
        title="工作台"
        subtitle="经营概览、库存预警与售后待办"
        extra={
          <Space wrap>
            <ChannelScopeSelect />
            <DatePicker.RangePicker
              value={range}
              allowClear={false}
              onChange={(values) => {
                if (values?.[0] && values?.[1]) setRange([values[0], values[1]]);
              }}
            />
          </Space>
        }
      />

      {canOrder ? (
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12} lg={6}>
            <StatCard title="GMV（含税）" value={formatMoney(data?.gross_sales_amount)} loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} />
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <StatCard title="订单数" value={data?.order_count ?? 0} loading={query.isLoading} hint={`已支付 ${data?.paid_order_count ?? 0} 单`} />
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <StatCard title="客单价" value={formatMoney(data?.avg_order_value)} loading={query.isLoading} />
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <StatCard
              title="支付成功率"
              value={data?.conversion_rate !== undefined ? `${((data.conversion_rate ?? 0) * 100).toFixed(1)}%` : '-'}
              loading={query.isLoading}
            />
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <StatCard title="净销售额" value={formatMoney(data?.net_sales_amount)} loading={query.isLoading} />
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <StatCard title="退款金额" value={formatMoney(data?.refund_amount)} loading={query.isLoading} />
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <StatCard title="新增客户" value={data?.new_customers ?? 0} loading={query.isLoading} />
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <StatCard title="低库存 SKU" value={data?.low_stock_count ?? 0} loading={query.isLoading} hint="低于安全库存" />
          </Col>
        </Row>
      ) : (
        <Card>
          <Typography.Text type="secondary">当前账号无订单读取权限，经营卡片已隐藏。</Typography.Text>
        </Card>
      )}

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <ChartCard
            title="商品销售排行"
            loading={query.isLoading}
            error={query.error}
            onRetry={() => void query.refetch()}
            empty={topProducts.length === 0}
            summary={topProducts.length > 0 ? `共 ${topProducts.length} 个商品上榜，首位 ${topProducts[0]?.label}` : undefined}
          >
            <BarList items={topProducts} />
          </ChartCard>
        </Col>
        <Col xs={24} lg={12}>
          <ChartCard
            title="渠道结构"
            loading={query.isLoading}
            error={query.error}
            onRetry={() => void query.refetch()}
            empty={channels.length === 0}
            summary={channels.length > 0 ? `共 ${channels.length} 个渠道有数据` : undefined}
          >
            <BarList items={channels} />
          </ChartCard>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        {canInventory ? (
          <Col xs={24} lg={12}>
            <StatCard title="库存提示" value={`${data?.low_stock_count ?? 0} 个 SKU 低于安全库存`} loading={query.isLoading} hint="前往库存总览进行补货调整" />
          </Col>
        ) : null}
        {canAfterSales ? (
          <Col xs={24} lg={12}>
            <StatCard title="售后待办" value={`${data?.pending_after_sales_count ?? 0} 单待处理`} loading={query.isLoading} hint="前往售后工单处理" />
          </Col>
        ) : null}
      </Row>

      <Card style={{ marginTop: 16 }}>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          金额展示：GMV {formatMoney(data?.gross_sales_amount)} · 折扣 {formatMoney(data?.discount_amount)} · 数据生成时间 {data?.generated_at ?? '-'}
        </Typography.Text>
      </Card>
    </div>
  );
}
