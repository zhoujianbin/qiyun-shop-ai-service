import App from 'antd/es/app';
import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Tag from 'antd/es/tag';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { productsApi } from '@/api/endpoints/products';
import { catalogApi } from '@/api/endpoints/catalog';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { DataTable } from '@/components/data/DataTable';
import { FilterBar } from '@/components/data/FilterBar';
import { PageHeader } from '@/components/common/PageHeader';
import { PermissionGate } from '@/components/common/PermissionGate';
import { StatusTag } from '@/components/common/StatusTag';
import { MoneyText } from '@/components/common/MoneyText';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { useUrlFilters } from '@/hooks/useUrlFilters';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { errorMessage } from '@/api/errors';
import { formatDateTime } from '@/utils/datetime';
import { useTrack } from '@/hooks/useTrack';
import { PRODUCT_STATUS_OPTIONS, PRODUCT_TYPE_OPTIONS } from '@/constants/productStatus';
import { P } from '@/types/permissions';
import { ROUTES } from '@/constants/routes';
import type { Product } from '@/types/domain';

interface ProductFilters extends Record<string, string | undefined> {
  keyword?: string;
  status?: string;
  category_id?: string;
  product_type?: string;
}

/** B 端商品列表：筛选/分页/批量上下架，筛选写入 URL。 */
export default function ProductListPage() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const track = useTrack();
  const url = useUrlFilters<ProductFilters>({ keyword: undefined, status: undefined, category_id: undefined, product_type: undefined });
  const [selectedKeys, setSelectedKeys] = useState<number[]>([]);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkTarget, setBulkTarget] = useState<'ON_SALE' | 'OFF_SHELF'>('ON_SALE');

  const params = {
    keyword: url.filters.keyword,
    status: url.filters.status,
    category_id: url.filters.category_id,
    product_type: url.filters.product_type,
    page: url.page,
    page_size: url.pageSize,
  };

  const query = useQuery({
    queryKey: queryKeys.products.list(params),
    queryFn: ({ signal }) => productsApi.list({ ...params, signal }),
  });

  const categoryQuery = useQuery({
    queryKey: queryKeys.catalog.categories(),
    queryFn: ({ signal }) => catalogApi.categories({ signal }),
    staleTime: 5 * 60 * 1000,
  });

  const bulkMutation = useIdempotentMutation(
    async (vars: { ids: number[]; target: 'ON_SALE' | 'OFF_SHELF' }) => {
      for (const id of vars.ids) {
        if (vars.target === 'ON_SALE') await productsApi.publish(id);
        else await productsApi.unpublish(id);
      }
      return vars.ids.length;
    },
    {
      onSuccess: async (count) => {
        message.success(`已处理 ${count} 个商品`);
        track('product_bulk_status_change', { result: 'success' });
        setBulkOpen(false);
        setSelectedKeys([]);
        bulkMutation.resetKey();
        await queryClient.invalidateQueries({ queryKey: ['products'] });
      },
      onError: (error) => message.error(errorMessage(error)),
    },
  );

  const columns: ColumnsType<Product> = [
    {
      title: '商品',
      key: 'name',
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Typography.Text strong>{record.name}</Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>{record.spu_code}</Typography.Text>
        </Space>
      ),
    },
    { title: '产品线', dataIndex: 'product_line', key: 'product_line', render: (value?: string) => value ?? '-' },
    { title: '型号', dataIndex: 'model_code', key: 'model_code', render: (value?: string) => value ?? '-' },
    {
      title: '价格区间',
      key: 'price',
      render: (_, record) => <MoneyText value={record.min_price} />,
    },
    { title: '状态', dataIndex: 'status', key: 'status', render: (value: string) => <StatusTag kind="product" value={value} /> },
    { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', render: (value?: string) => formatDateTime(value) },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_, record) => (
        <Space>
          <Button type="link" onClick={() => navigate(ROUTES.adminProductEdit(record.id))}>编辑</Button>
          <PermissionGate permission={P.productWrite} mode="disable" fallbackReason="需要商品写权限">
            <Button
              type="link"
              onClick={async () => {
                try {
                  if (record.status === 'ON_SALE') await productsApi.unpublish(record.id);
                  else await productsApi.publish(record.id);
                  message.success('状态已更新');
                  await queryClient.invalidateQueries({ queryKey: ['products'] });
                } catch (error) {
                  message.error(errorMessage(error));
                }
              }}
            >
              {record.status === 'ON_SALE' ? '下架' : '上架'}
            </Button>
          </PermissionGate>
        </Space>
      ),
    },
  ];

  return (
    <div className="qy-page">
      <PageHeader
        title="商品管理"
        subtitle="SPU / 价格 / 渠道与上下架"
        extra={
          <PermissionGate permission={P.productWrite} mode="disable" fallbackReason="需要商品写权限">
            <Button type="primary" onClick={() => navigate(ROUTES.adminProductNew)}>新建商品</Button>
          </PermissionGate>
        }
      />
      <FilterBar onReset={() => url.reset()}>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">商品名称 / SPU</span>
          <Input.Search allowClear style={{ width: 220 }} placeholder="模糊匹配" defaultValue={url.filters.keyword} onSearch={(value) => url.setFilter('keyword', value || undefined)} />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">状态</span>
          <Select allowClear style={{ width: 140 }} placeholder="全部" value={url.filters.status} options={PRODUCT_STATUS_OPTIONS} onChange={(value) => url.setFilter('status', value)} />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">产品类型</span>
          <Select allowClear style={{ width: 160 }} placeholder="全部" value={url.filters.product_type} options={PRODUCT_TYPE_OPTIONS} onChange={(value) => url.setFilter('product_type', value)} />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">类目 ID</span>
          <Select
            allowClear
            showSearch
            optionFilterProp="label"
            style={{ width: 180 }}
            placeholder="全部"
            value={url.filters.category_id ? Number(url.filters.category_id) : undefined}
            loading={categoryQuery.isLoading}
            options={(categoryQuery.data ?? []).map((category) => ({ value: category.id, label: category.name }))}
            onChange={(value) => url.setFilter('category_id', value ?? undefined)}
          />
        </Space>
      </FilterBar>

      <DataTable<Product>
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
        emptyTitle="没有符合条件的商品"
        emptyAction={
          <Space>
            <Button onClick={() => url.reset()}>清空筛选</Button>
            <PermissionGate permission={P.productWrite} mode="disable" fallbackReason="需要商品写权限">
              <Button type="primary" onClick={() => navigate(ROUTES.adminProductNew)}>新建商品</Button>
            </PermissionGate>
          </Space>
        }
        rowSelection={{
          selectedRowKeys: selectedKeys,
          onChange: (keys) => setSelectedKeys(keys as number[]),
        }}
        toolbar={
          selectedKeys.length > 0 ? (
            <Space>
              <Typography.Text>已选 {selectedKeys.length} 项</Typography.Text>
              <PermissionGate permission={P.productWrite} mode="disable" fallbackReason="需要商品写权限">
                <Button onClick={() => { setBulkTarget('ON_SALE'); setBulkOpen(true); }}>批量上架</Button>
              </PermissionGate>
              <PermissionGate permission={P.productWrite} mode="disable" fallbackReason="需要商品写权限">
                <Button onClick={() => { setBulkTarget('OFF_SHELF'); setBulkOpen(true); }}>批量下架</Button>
              </PermissionGate>
            </Space>
          ) : null
        }
      />

      <ConfirmDialog
        open={bulkOpen}
        title={bulkTarget === 'ON_SALE' ? '批量上架商品' : '批量下架商品'}
        danger={bulkTarget === 'OFF_SHELF'}
        confirmText="确认执行"
        loading={bulkMutation.isPending}
        impact={
          <Space direction="vertical">
            <Typography.Text>将影响 {selectedKeys.length} 个商品，目标状态：<Tag color={bulkTarget === 'ON_SALE' ? 'success' : 'warning'}>{bulkTarget === 'ON_SALE' ? '在售' : '已下架'}</Tag></Typography.Text>
            <Typography.Text type="secondary">下架后 C 端不可购买；请确认渠道范围与库存。</Typography.Text>
          </Space>
        }
        onConfirm={() => bulkMutation.mutate({ ids: selectedKeys, target: bulkTarget })}
        onCancel={() => setBulkOpen(false)}
      />
    </div>
  );
}
