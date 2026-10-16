import Input from 'antd/es/input';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useQuery } from '@tanstack/react-query';
import { inventoryApi } from '@/api/endpoints/inventory';
import { warehousesApi } from '@/api/endpoints/warehouses';
import { queryKeys } from '@/api/queryKeys';
import { DataTable } from '@/components/data/DataTable';
import { FilterBar } from '@/components/data/FilterBar';
import { PageHeader } from '@/components/common/PageHeader';
import { useUrlFilters } from '@/hooks/useUrlFilters';
import { formatDateTime } from '@/utils/datetime';
import { CHANGE_TYPE_LABELS } from '@/constants/productStatus';
import { CHANGE_TYPES } from '@/types/status';
import type { InventoryLedgerEntry } from '@/types/domain';

interface LedgerFilters extends Record<string, string | undefined> {
  sku_id?: string;
  warehouse_id?: string;
  change_type?: string;
}

/** B 端库存流水：只增不改，记录每次变动与结存。 */
export default function InventoryLedgerPage() {
  const url = useUrlFilters<LedgerFilters>({ sku_id: undefined, warehouse_id: undefined, change_type: undefined });

  const params = {
    sku_id: url.filters.sku_id,
    warehouse_id: url.filters.warehouse_id,
    change_type: url.filters.change_type,
    page: url.page,
    page_size: url.pageSize,
  };

  const query = useQuery({
    queryKey: queryKeys.inventory.ledger(params),
    queryFn: ({ signal }) => inventoryApi.ledger({ ...params, signal }),
  });

  const warehouseQuery = useQuery({
    queryKey: queryKeys.warehouses.list({ page: 1, page_size: 100 }),
    queryFn: ({ signal }) => warehousesApi.list({ page: 1, page_size: 100, signal }),
    staleTime: 5 * 60 * 1000,
  });

  const columns: ColumnsType<InventoryLedgerEntry> = [
    { title: '时间', dataIndex: 'created_at', key: 'created_at', render: (value: string) => formatDateTime(value) },
    { title: 'SKU ID', dataIndex: 'sku_id', key: 'sku_id' },
    { title: '仓库', dataIndex: 'warehouse_id', key: 'warehouse_id' },
    { title: '类型', dataIndex: 'change_type', key: 'change_type', render: (value: string) => CHANGE_TYPE_LABELS[value as keyof typeof CHANGE_TYPE_LABELS] ?? value },
    {
      title: '变动',
      dataIndex: 'qty_delta',
      key: 'qty_delta',
      render: (value: number) => <Typography.Text type={value >= 0 ? 'success' : 'danger'}>{value > 0 ? `+${value}` : value}</Typography.Text>,
    },
    { title: '结存', dataIndex: 'qty_after', key: 'qty_after' },
    { title: '关联单据', key: 'ref', render: (_, record) => (record.ref_type ? `${record.ref_type} ${record.ref_id ?? ''}` : '-') },
    { title: '备注', dataIndex: 'remark', key: 'remark', render: (value?: string) => value ?? '-' },
  ];

  return (
    <div className="qy-page">
      <PageHeader title="库存流水" subtitle="只追加流水，用于对账与追溯" breadcrumb={[{ label: '库存中心' }, { label: '库存流水' }]} />
      <FilterBar onReset={() => url.reset()}>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">SKU ID</span>
          <Input.Search allowClear style={{ width: 160 }} placeholder="精确" defaultValue={url.filters.sku_id} onSearch={(value) => url.setFilter('sku_id', value || undefined)} />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">仓库</span>
          <Select
            allowClear
            style={{ width: 180 }}
            placeholder="全部"
            value={url.filters.warehouse_id ? Number(url.filters.warehouse_id) : undefined}
            options={(warehouseQuery.data?.items ?? []).map((warehouse) => ({ value: warehouse.id, label: warehouse.name }))}
            onChange={(value) => url.setFilter('warehouse_id', value ?? undefined)}
          />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">变动类型</span>
          <Select
            allowClear
            style={{ width: 160 }}
            placeholder="全部"
            value={url.filters.change_type}
            options={CHANGE_TYPES.map((value) => ({ value, label: CHANGE_TYPE_LABELS[value] }))}
            onChange={(value) => url.setFilter('change_type', value)}
          />
        </Space>
      </FilterBar>
      <DataTable<InventoryLedgerEntry>
        rowKey="id"
        columns={columns}
        data={query.data?.items ?? []}
        loading={query.isLoading}
        error={query.error}
        onRetry={() => void query.refetch()}
        total={query.data?.meta?.total ?? 0}
        page={url.page}
        pageSize={url.pageSize}
        onPageChange={(page, pageSize) => { url.setPage(page); if (pageSize !== url.pageSize) url.setPageSize(pageSize); }}
        emptyTitle="暂无库存流水"
      />
    </div>
  );
}
