import App from 'antd/es/app';
import Button from 'antd/es/button';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import InputNumber from 'antd/es/input-number';
import Modal from 'antd/es/modal';
import Space from 'antd/es/space';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { catalogApi } from '@/api/endpoints/catalog';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { DataTable } from '@/components/data/DataTable';
import { PageHeader } from '@/components/common/PageHeader';
import { PermissionGate } from '@/components/common/PermissionGate';
import { StatusTag } from '@/components/common/StatusTag';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { errorMessage } from '@/api/errors';
import { P } from '@/types/permissions';
import type { Brand, BrandCreateRequest } from '@/types/domain';

/** B 端品牌管理：品牌列表与新增。 */
export default function BrandPage() {
  const { message } = App.useApp();
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm<BrandCreateRequest>();

  const query = useQuery({
    queryKey: queryKeys.catalog.brands({ page: 1, page_size: 100 }),
    queryFn: ({ signal }) => catalogApi.brands({ page: 1, page_size: 100, signal }),
  });

  const createMutation = useIdempotentMutation((body: BrandCreateRequest) => catalogApi.createBrand(body), {
    onSuccess: async () => {
      message.success('品牌已创建');
      setOpen(false);
      createMutation.resetKey();
      await queryClient.invalidateQueries({ queryKey: ['catalog'] });
    },
    onError: (error) => message.error(errorMessage(error)),
  });

  const columns: ColumnsType<Brand> = [
    { title: '品牌名称', dataIndex: 'name', key: 'name' },
    { title: '品牌编码', dataIndex: 'code', key: 'code' },
    { title: '排序', dataIndex: 'sort_order', key: 'sort_order', width: 80 },
    { title: '状态', dataIndex: 'status', key: 'status', width: 100, render: (value: string) => <StatusTag kind="product" value={value === 'ACTIVE' ? 'ON_SALE' : 'OFF_SHELF'} /> },
  ];

  return (
    <div className="qy-page">
      <PageHeader
        title="品牌管理"
        subtitle="商品品牌字典"
        extra={
          <PermissionGate permission={P.productWrite} mode="disable" fallbackReason="需要商品写权限">
            <Button type="primary" onClick={() => { form.resetFields(); setOpen(true); }}>新建品牌</Button>
          </PermissionGate>
        }
      />
      <DataTable<Brand>
        rowKey="id"
        columns={columns}
        data={query.data?.items ?? []}
        loading={query.isLoading}
        error={query.error}
        onRetry={() => void query.refetch()}
        showPagination={false}
        emptyTitle="暂无品牌"
      />
      <Modal
        open={open}
        title="新建品牌"
        okText="保存"
        cancelText="取消"
        confirmLoading={createMutation.isPending}
        onCancel={() => setOpen(false)}
        onOk={() => {
          void form.validateFields().then((values) => createMutation.mutate(values));
        }}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Space size={12} wrap>
            <Form.Item label="品牌编码" name="code" rules={[{ required: true, message: '请输入品牌编码' }]}>
              <Input style={{ width: 200 }} placeholder="如：QYUN" />
            </Form.Item>
            <Form.Item label="品牌名称" name="name" rules={[{ required: true, message: '请输入品牌名称' }]}>
              <Input style={{ width: 200 }} placeholder="如：栖云" />
            </Form.Item>
            <Form.Item label="排序" name="sort_order">
              <InputNumber min={0} style={{ width: 120 }} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </div>
  );
}
