import Button from 'antd/es/button';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import type { ColumnsType } from 'antd/es/table';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { customersApi } from '@/api/endpoints/customers';
import { queryKeys } from '@/api/queryKeys';
import { DataTable } from '@/components/data/DataTable';
import { FilterBar } from '@/components/data/FilterBar';
import { PageHeader } from '@/components/common/PageHeader';
import { MaskedText } from '@/components/common/MaskedText';
import { MoneyText } from '@/components/common/MoneyText';
import { useUrlFilters } from '@/hooks/useUrlFilters';
import { formatDateTime } from '@/utils/datetime';
import { ROUTES } from '@/constants/routes';
import type { Customer } from '@/types/domain';

interface CustomerFilters extends Record<string, string | undefined> {
  keyword?: string;
  status?: string;
}

/** B 端客户列表：脱敏展示，敏感字段不做本地还原。 */
export default function CustomerListPage() {
  const navigate = useNavigate();
  const url = useUrlFilters<CustomerFilters>({ keyword: undefined, status: undefined });

  const params = {
    keyword: url.filters.keyword,
    status: url.filters.status,
    page: url.page,
    page_size: url.pageSize,
  };

  const query = useQuery({
    queryKey: queryKeys.customers.list(params),
    queryFn: ({ signal }) => customersApi.list({ ...params, signal }),
  });

  const columns: ColumnsType<Customer> = [
    { title: '客户编号', dataIndex: 'customer_no', key: 'customer_no' },
    { title: '昵称/姓名', key: 'name', render: (_, record) => record.real_name ?? record.nickname ?? '-' },
    { title: '手机号', dataIndex: 'mobile_masked', key: 'mobile_masked', render: (value?: string) => <MaskedText value={value} /> },
    { title: '订单数', dataIndex: 'total_order_count', key: 'total_order_count', render: (value?: number) => value ?? 0 },
    { title: '累计消费', dataIndex: 'total_paid_amount', key: 'total_paid_amount', render: (value?: string) => <MoneyText value={value} /> },
    { title: '注册时间', dataIndex: 'created_at', key: 'created_at', render: (value?: string) => formatDateTime(value) },
    { title: '状态', dataIndex: 'status', key: 'status', render: (value: string) => (value === 'ACTIVE' ? '正常' : '停用') },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, record) => <Button type="link" onClick={() => navigate(ROUTES.adminCustomerProfile(record.id))}>档案</Button>,
    },
  ];

  return (
    <div className="qy-page">
      <PageHeader title="客户档案" subtitle="客户信息、订单与售后归集" />
      <FilterBar onReset={() => url.reset()}>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">关键词</span>
          <Input.Search allowClear style={{ width: 220 }} placeholder="客户编号 / 昵称 / 手机后四位" defaultValue={url.filters.keyword} onSearch={(value) => url.setFilter('keyword', value || undefined)} />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">状态</span>
          <Select allowClear style={{ width: 140 }} placeholder="全部" value={url.filters.status} options={[{ value: 'ACTIVE', label: '正常' }, { value: 'DISABLED', label: '停用' }]} onChange={(value) => url.setFilter('status', value)} />
        </Space>
      </FilterBar>
      <DataTable<Customer>
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
        emptyTitle="暂无客户记录"
      />
    </div>
  );
}
