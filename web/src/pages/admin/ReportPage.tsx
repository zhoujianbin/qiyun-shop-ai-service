import Card from 'antd/es/card';
import Col from 'antd/es/col';
import DatePicker from 'antd/es/date-picker';
import Row from 'antd/es/row';
import Space from 'antd/es/space';
import Table from 'antd/es/table';
import type { ColumnsType } from 'antd/es/table';
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
import { PermissionGate } from '@/components/common/PermissionGate';
import { useChannelScope } from '@/hooks/useChannelScope';
import { usePermission } from '@/hooks/usePermission';
import { downloadCsv } from '@/utils/download';
import { formatMoney } from '@/utils/money';
import { pickNumber, pickString } from '@/utils/report';
import { dayjs, formatDate } from '@/utils/datetime';
import { P } from '@/types/permissions';
import type { SalesDailyReport } from '@/types/domain';

/** B 端报表工作台：销售趋势、库存健康、售后分析；每个卡片按权限可见。 */
export default function ReportPage() {
  const [range, setRange] = useState<[Dayjs, Dayjs]>([dayjs().subtract(29, 'day'), dayjs()]);
  const { activeChannelId } = useChannelScope();
  const canOrder = usePermission(P.orderRead);
  const canInventory = usePermission(P.inventoryRead);
  const canAfterSales = usePermission(P.aftersalesRead);

  const baseParams = {
    date_from: range[0].format('YYYY-MM-DD'),
    date_to: range[1].format('YYYY-MM-DD'),
    channel_account_id: activeChannelId ?? undefined,
  };

  const salesQuery = useQuery({
    queryKey: queryKeys.reports.salesDaily(baseParams),
    queryFn: ({ signal }) => reportsApi.salesDaily({ ...baseParams, page: 1, page_size: 90, signal }),
    enabled: canOrder,
  });
  const inventoryQuery = useQuery({
    queryKey: queryKeys.reports.inventory({ warehouse_id: undefined }),
    queryFn: ({ signal }) => reportsApi.inventory({ signal }),
    enabled: canInventory,
  });
  const afterSalesQuery = useQuery({
    queryKey: queryKeys.reports.afterSales(baseParams),
    queryFn: ({ signal }) => reportsApi.afterSales({ ...baseParams, signal }),
    enabled: canAfterSales,
  });

  const daily = salesQuery.data?.items ?? [];
  const totalGmv = daily.reduce((sum, item) => sum + Number(item.gmv || 0), 0);
  const trendItems = daily.slice(-14).map((item) => ({ label: formatDate(item.date), value: Number(item.gmv || 0), money: true }));

  const inventoryData = inventoryQuery.data;
  const afterSalesData = afterSalesQuery.data;

  const columns: ColumnsType<SalesDailyReport> = [
    { title: '日期', dataIndex: 'date', key: 'date', render: (value: string) => formatDate(value) },
    { title: '订单数', dataIndex: 'order_count', key: 'order_count' },
    { title: '已支付订单', dataIndex: 'paid_order_count', key: 'paid_order_count' },
    { title: 'GMV', dataIndex: 'gmv', key: 'gmv', render: (value: string) => formatMoney(value) },
    { title: '退款', dataIndex: 'refund_amount', key: 'refund_amount', render: (value?: string) => formatMoney(value) },
    { title: '新增客户', dataIndex: 'new_customers', key: 'new_customers' },
  ];

  const funnelItems = afterSalesData
    ? [
        { label: '申请', value: afterSalesData.application_count },
        { label: '完成', value: afterSalesData.completed_count ?? 0 },
        { label: '驳回', value: afterSalesData.rejected_count ?? 0 },
      ]
    : [];

  return (
    <div className="qy-page">
      <PageHeader
        title="报表工作台"
        subtitle="销售趋势、商品排行、售后与库存健康"
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
            <PermissionGate permission={P.reportRead} mode="disable" fallbackReason="需要报表读取权限">
              <a
                onClick={() =>
                  downloadCsv(
                    'sales_daily_report',
                    ['日期', '订单数', '已支付', 'GMV', '退款', '新增客户'],
                    daily.map((item) => [item.date, item.order_count, item.paid_order_count ?? 0, item.gmv, item.refund_amount ?? '0.00', item.new_customers ?? 0]),
                  )
                }
              >
                导出销售日报
              </a>
            </PermissionGate>
          </Space>
        }
      />

      {canOrder ? (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={24} sm={12} lg={6}>
              <StatCard title="区间 GMV" value={formatMoney(String(totalGmv))} loading={salesQuery.isLoading} error={salesQuery.error} onRetry={() => void salesQuery.refetch()} />
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <StatCard title="日均 GMV" value={formatMoney(String(daily.length > 0 ? totalGmv / daily.length : 0))} loading={salesQuery.isLoading} />
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <StatCard title="区间订单数" value={daily.reduce((sum, item) => sum + Number(item.order_count || 0), 0)} loading={salesQuery.isLoading} />
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <StatCard title="区间新增客户" value={daily.reduce((sum, item) => sum + Number(item.new_customers || 0), 0)} loading={salesQuery.isLoading} />
            </Col>
          </Row>
          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} lg={14}>
              <ChartCard
                title="销售趋势（近 14 天）"
                loading={salesQuery.isLoading}
                error={salesQuery.error}
                onRetry={() => void salesQuery.refetch()}
                empty={trendItems.length === 0}
                summary={trendItems.length > 0 ? `近 14 天最高 ${formatMoney(String(Math.max(...trendItems.map((i) => i.value))))}` : undefined}
              >
                <BarList items={trendItems} />
              </ChartCard>
            </Col>
            <Col xs={24} lg={10}>
              <ChartCard
                title="售后漏斗"
                loading={afterSalesQuery.isLoading}
                error={afterSalesQuery.error}
                onRetry={() => void afterSalesQuery.refetch()}
                empty={funnelItems.length === 0}
                summary={`申请 ${afterSalesData?.application_count ?? 0}，完成 ${afterSalesData?.completed_count ?? 0}`}
              >
                <BarList items={funnelItems} />
              </ChartCard>
            </Col>
          </Row>
        </>
      ) : (
        <Card>当前账号无订单读取权限，经营类图表已隐藏。</Card>
      )}

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        {canInventory ? (
          <Col xs={24} lg={12}>
            <ChartCard
              title="库存健康"
              loading={inventoryQuery.isLoading}
              error={inventoryQuery.error}
              onRetry={() => void inventoryQuery.refetch()}
              empty={!inventoryData}
              summary={inventoryData ? `可售 ${inventoryData.total_available_qty}，低库存 ${inventoryData.low_stock_count ?? 0}` : undefined}
            >
              <BarList
                items={[
                  { label: '可售', value: inventoryData?.total_available_qty ?? 0 },
                  { label: '锁定', value: inventoryData?.total_reserved_qty ?? 0 },
                  { label: '在途', value: inventoryData?.total_in_transit_qty ?? 0 },
                  { label: '低库存 SKU', value: inventoryData?.low_stock_count ?? 0 },
                  { label: '缺货 SKU', value: inventoryData?.out_of_stock_count ?? 0 },
                ]}
              />
            </ChartCard>
          </Col>
        ) : null}
        {canAfterSales ? (
          <Col xs={24} lg={12}>
            <ChartCard
              title="售后类型分布"
              loading={afterSalesQuery.isLoading}
              error={afterSalesQuery.error}
              onRetry={() => void afterSalesQuery.refetch()}
              empty={(afterSalesData?.by_type ?? []).length === 0}
            >
              <BarList
                items={(afterSalesData?.by_type ?? []).map((item) => {
                  const record = item as Record<string, unknown>;
                  return { label: pickString(record, ['type', 'name', 'status'], '类型'), value: pickNumber(record, ['count', 'application_count', 'value']) };
                })}
              />
            </ChartCard>
          </Col>
        ) : null}
      </Row>

      {canOrder ? (
        <Card title="销售日报明细" style={{ marginTop: 16 }}>
          <Table<SalesDailyReport> rowKey="date" columns={columns} dataSource={daily} loading={salesQuery.isLoading} pagination={{ pageSize: 15 }} />
        </Card>
      ) : null}
    </div>
  );
}
