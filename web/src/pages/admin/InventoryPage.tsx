import App from 'antd/es/app';
import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Switch from 'antd/es/switch';
import Tag from 'antd/es/tag';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { inventoryApi } from '@/api/endpoints/inventory';
import { warehousesApi } from '@/api/endpoints/warehouses';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { DataTable } from '@/components/data/DataTable';
import { FilterBar } from '@/components/data/FilterBar';
import { PageHeader } from '@/components/common/PageHeader';
import { PermissionGate } from '@/components/common/PermissionGate';
import { StockAdjustDialog } from '@/components/inventory/StockAdjustDialog';
import { useUrlFilters } from '@/hooks/useUrlFilters';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { toApiError, errorMessage } from '@/api/errors';
import { useChannelScope } from '@/hooks/useChannelScope';
import { useTrack } from '@/hooks/useTrack';
import { P } from '@/types/permissions';
import type { InventoryItem, StockAdjustRequest } from '@/types/domain';

interface InventoryFilters extends Record<string, string | undefined> {
  sku_code?: string;
  warehouse_id?: string;
  low_stock?: string;
}

/** B 端库存总览：可售/锁定/在途/安全库存分列，调整弹窗落流水。 */
export default function InventoryPage() {
  const { message } = App.useApp();
  const track = useTrack();
  const { activeChannelId } = useChannelScope();
  const url = useUrlFilters<InventoryFilters>({ sku_code: undefined, warehouse_id: undefined, low_stock: undefined });
  const [adjustItem, setAdjustItem] = useState<InventoryItem | null>(null);
  const [conflict, setConflict] = useState(false);

  const params = {
    sku_code: url.filters.sku_code,
    warehouse_id: url.filters.warehouse_id,
    low_stock: url.filters.low_stock === 'true' ? true : undefined,
    channel_account_id: activeChannelId ?? undefined,
    page: url.page,
    page_size: url.pageSize,
  };

  const query = useQuery({
    queryKey: queryKeys.inventory.list(params),
    queryFn: ({ signal }) => inventoryApi.list({ ...params, signal }),
  });

  const warehouseQuery = useQuery({
    queryKey: queryKeys.warehouses.list({ page: 1, page_size: 100 }),
    queryFn: ({ signal }) => warehousesApi.list({ page: 1, page_size: 100, signal }),
    staleTime: 5 * 60 * 1000,
  });

  const adjustMutation = useIdempotentMutation((body: StockAdjustRequest) => inventoryApi.adjust(body), {
    onSuccess: async (entry) => {
      message.success(`库存调整成功，流水号 #${entry.id}`);
      track('stock_adjust_success', { sku_id: entry.sku_id, warehouse_id: entry.warehouse_id, result: 'success' });
      setAdjustItem(null);
      setConflict(false);
      adjustMutation.resetKey();
      await queryClient.invalidateQueries({ queryKey: ['inventory'] });
      await queryClient.invalidateQueries({ queryKey: ['skus'] });
    },
    onError: (error) => {
      const apiError = toApiError(error);
      if (apiError.isConflict) {
        setConflict(true);
        track('stock_adjust_conflict', { result: 'conflict' });
        message.warning('库存已变化，请刷新后重试');
        void query.refetch();
      } else {
        message.error(errorMessage(error));
      }
    },
  });

  const columns: ColumnsType<InventoryItem> = [
    { title: 'SKU 编码', dataIndex: 'sku_code', key: 'sku_code', render: (value?: string) => value ?? '-' },
    { title: '商品', dataIndex: 'product_name', key: 'product_name', render: (value?: string) => value ?? '-' },
    { title: '规格', dataIndex: 'sku_name', key: 'sku_name', render: (value?: string) => value ?? '-' },
    { title: '仓库', dataIndex: 'warehouse_name', key: 'warehouse_name', render: (value?: string) => value ?? '-' },
    {
      title: '可售',
      dataIndex: 'qty_available',
      key: 'qty_available',
      render: (value: number, record) => (
        <Space size={6}>
          <Typography.Text strong>{value}</Typography.Text>
          {record.is_low_stock ? <Tag color="warning">低于安全库存</Tag> : null}
        </Space>
      ),
    },
    { title: '锁定', dataIndex: 'qty_reserved', key: 'qty_reserved' },
    { title: '在途', dataIndex: 'qty_in_transit', key: 'qty_in_transit' },
    { title: '安全库存', dataIndex: 'safety_stock', key: 'safety_stock' },
    { title: '版本', dataIndex: 'version', key: 'version', width: 80 },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_, record) => (
        <PermissionGate permission={P.inventoryWrite} mode="disable" fallbackReason="需要库存写权限">
          <Button
            type="link"
            onClick={() => {
              setConflict(false);
              setAdjustItem(record);
              track('stock_adjust_open', { sku_id: record.sku_id, warehouse_id: record.warehouse_id });
            }}
          >
            库存调整
          </Button>
        </PermissionGate>
      ),
    },
  ];

  return (
    <div className="qy-page">
      <PageHeader
        title="库存总览"
        subtitle="可售 / 锁定 / 在途 / 安全库存；库存只经调整流水变化"
        breadcrumb={[{ label: '库存中心' }, { label: '库存总览' }]}
      />
      <FilterBar onReset={() => url.reset()}>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">SKU 编码</span>
          <Input.Search allowClear style={{ width: 220 }} placeholder="精确 / 前缀匹配" defaultValue={url.filters.sku_code} onSearch={(value) => url.setFilter('sku_code', value || undefined)} />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">仓库</span>
          <Select
            allowClear
            showSearch
            optionFilterProp="label"
            style={{ width: 200 }}
            placeholder="全部仓库"
            value={url.filters.warehouse_id ? Number(url.filters.warehouse_id) : undefined}
            loading={warehouseQuery.isLoading}
            options={(warehouseQuery.data?.items ?? []).map((warehouse) => ({ value: warehouse.id, label: warehouse.name }))}
            onChange={(value) => url.setFilter('warehouse_id', value ?? undefined)}
          />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">仅看低库存</span>
          <Switch checked={url.filters.low_stock === 'true'} onChange={(checked) => url.setFilter('low_stock', checked ? 'true' : undefined)} />
        </Space>
      </FilterBar>

      <DataTable<InventoryItem>
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
        emptyTitle="没有符合条件的库存记录"
      />

      <StockAdjustDialog
        open={Boolean(adjustItem)}
        item={adjustItem}
        warehouses={warehouseQuery.data?.items ?? []}
        loading={adjustMutation.isPending}
        conflict={conflict}
        onCancel={() => setAdjustItem(null)}
        onSubmit={(payload) => adjustMutation.mutate(payload)}
      />
    </div>
  );
}
