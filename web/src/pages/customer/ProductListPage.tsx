import Col from 'antd/es/col';
import Input from 'antd/es/input';
import Pagination from 'antd/es/pagination';
import Row from 'antd/es/row';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import { useQuery } from '@tanstack/react-query';
import { useUrlFilters } from '@/hooks/useUrlFilters';
import { productsApi } from '@/api/endpoints/products';
import { catalogApi } from '@/api/endpoints/catalog';
import { queryKeys } from '@/api/queryKeys';
import { ProductCard } from '@/components/product/ProductCard';
import { PageHeader } from '@/components/common/PageHeader';
import { EmptyState } from '@/components/common/EmptyState';
import { ErrorState } from '@/components/common/ErrorState';
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton';
import { FilterBar } from '@/components/data/FilterBar';
import { PRODUCT_TYPE_OPTIONS } from '@/constants/productStatus';
import type { Category } from '@/types/domain';

interface ProductFilters extends Record<string, string | undefined> {
  keyword?: string;
  product_type?: string;
  category_id?: string;
  product_line?: string;
  sort?: string;
}

function flattenCategories(nodes: Category[]): Array<{ label: string; value: number }> {
  const out: Array<{ label: string; value: number }> = [];
  const walk = (list: Category[], prefix: string) => {
    list.forEach((node) => {
      out.push({ label: `${prefix}${node.name}`, value: node.id });
      if (node.children && node.children.length > 0) walk(node.children, `${prefix}${node.name} / `);
    });
  };
  walk(nodes, '');
  return out;
}

/** C 端商品列表：筛选/排序/分页，筛选条件写入 URL。 */
export default function ProductListPage() {
  const url = useUrlFilters<ProductFilters>({ keyword: undefined, product_type: undefined, category_id: undefined, product_line: undefined, sort: undefined });

  const categoryQuery = useQuery({
    queryKey: queryKeys.catalog.categories(),
    queryFn: ({ signal }) => catalogApi.categories({ signal }),
    staleTime: 5 * 60 * 1000,
  });

  const params = {
    keyword: url.filters.keyword,
    product_type: url.filters.product_type,
    category_id: url.filters.category_id,
    product_line: url.filters.product_line,
    sort: url.sort,
    status: 'ON_SALE',
    page: url.page,
    page_size: url.pageSize,
  };

  const query = useQuery({
    queryKey: queryKeys.products.list(params),
    queryFn: ({ signal }) => productsApi.publicList({ ...params, signal }),
  });

  const items = query.data?.items ?? [];
  const total = query.data?.meta?.total ?? 0;

  return (
    <div className="qy-page" style={{ maxWidth: 1200, margin: '0 auto' }}>
      <PageHeader title="全部商品" subtitle="智能门锁、家用摄像头、清洁机器人、智能灯具、家庭网关、配件耗材" />
      <FilterBar onReset={() => url.reset()}>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">关键词</span>
          <Input.Search
            allowClear
            placeholder="商品名称 / SPU 编码"
            defaultValue={url.filters.keyword}
            style={{ width: 240 }}
            onSearch={(value) => url.setFilter('keyword', value || undefined)}
          />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">产品类型</span>
          <Select
            allowClear
            placeholder="全部"
            style={{ width: 160 }}
            value={url.filters.product_type || undefined}
            options={PRODUCT_TYPE_OPTIONS}
            onChange={(value) => url.setFilter('product_type', value)}
          />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">类目</span>
          <Select
            allowClear
            showSearch
            optionFilterProp="label"
            placeholder="全部"
            style={{ width: 200 }}
            value={url.filters.category_id ? Number(url.filters.category_id) : undefined}
            loading={categoryQuery.isLoading}
            options={flattenCategories(categoryQuery.data ?? [])}
            onChange={(value) => url.setFilter('category_id', value ?? undefined)}
          />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">排序</span>
          <Select
            style={{ width: 150 }}
            value={url.sort ?? 'updated_at:desc'}
            options={[
              { value: 'updated_at:desc', label: '最新上架' },
              { value: 'min_price:asc', label: '价格从低到高' },
              { value: 'min_price:desc', label: '价格从高到低' },
            ]}
            onChange={(value) => url.setSort(value)}
          />
        </Space>
      </FilterBar>

      {query.isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState title="没有符合条件的商品" description="可以清空筛选条件后重试" action={<a onClick={() => url.reset()}>清空筛选</a>} />
      ) : (
        <>
          <Row gutter={[16, 16]}>
            {items.map((product) => (
              <Col key={product.id} xs={12} sm={12} md={8} lg={6}>
                <ProductCard product={product} />
              </Col>
            ))}
          </Row>
          <div style={{ textAlign: 'right', marginTop: 16 }}>
            <Pagination
              current={url.page}
              pageSize={url.pageSize}
              total={total}
              showSizeChanger
              showTotal={(t) => `共 ${t} 件商品`}
              onChange={(page, pageSize) => {
                url.setPage(page);
                if (pageSize !== url.pageSize) url.setPageSize(pageSize);
              }}
            />
          </div>
        </>
      )}
    </div>
  );
}
