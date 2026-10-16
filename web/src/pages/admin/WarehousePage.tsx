import App from 'antd/es/app';
import Button from 'antd/es/button';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import InputNumber from 'antd/es/input-number';
import Modal from 'antd/es/modal';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { warehousesApi } from '@/api/endpoints/warehouses';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { DataTable } from '@/components/data/DataTable';
import { PageHeader } from '@/components/common/PageHeader';
import { PermissionGate } from '@/components/common/PermissionGate';
import { MaskedText } from '@/components/common/MaskedText';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { errorMessage } from '@/api/errors';
import { WAREHOUSE_TYPES } from '@/types/status';
import { P } from '@/types/permissions';
import type { Warehouse, WarehouseCreateRequest } from '@/types/domain';

const WAREHOUSE_TYPE_LABELS: Record<string, string> = { SELF: '自营仓', THIRD_PARTY: '三方仓', VIRTUAL: '虚拟仓' };

/** B 端仓库管理：仓库字典与新增。 */
export default function WarehousePage() {
  const { message } = App.useApp();
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm<WarehouseCreateRequest>();

  const query = useQuery({
    queryKey: queryKeys.warehouses.list({ page: 1, page_size: 100 }),
    queryFn: ({ signal }) => warehousesApi.list({ page: 1, page_size: 100, signal }),
  });

  const createMutation = useIdempotentMutation((body: WarehouseCreateRequest) => warehousesApi.create(body), {
    onSuccess: async () => {
      message.success('仓库已创建');
      setOpen(false);
      createMutation.resetKey();
      await queryClient.invalidateQueries({ queryKey: ['warehouses'] });
    },
    onError: (error) => message.error(errorMessage(error)),
  });

  const columns: ColumnsType<Warehouse> = [
    { title: '仓库名称', dataIndex: 'name', key: 'name' },
    { title: '编码', dataIndex: 'code', key: 'code' },
    { title: '类型', dataIndex: 'type', key: 'type', render: (value?: string) => (value ? WAREHOUSE_TYPE_LABELS[value] ?? value : '-') },
    { title: '区域', dataIndex: 'region', key: 'region', render: (value?: string) => value ?? '-' },
    { title: '联系人', dataIndex: 'contact_name', key: 'contact_name', render: (value?: string) => value ?? '-' },
    { title: '联系电话', dataIndex: 'contact_mobile_masked', key: 'contact_mobile_masked', render: (value?: string) => <MaskedText value={value} /> },
    { title: '优先级', dataIndex: 'priority', key: 'priority', width: 90 },
    { title: '状态', dataIndex: 'status', key: 'status', width: 100, render: (value: string) => (value === 'ACTIVE' ? '启用' : '停用') },
  ];

  return (
    <div className="qy-page">
      <PageHeader
        title="仓库管理"
        subtitle="自营仓 / 三方仓 / 虚拟仓"
        extra={
          <PermissionGate permission={P.inventoryWrite} mode="disable" fallbackReason="需要库存写权限">
            <Button type="primary" onClick={() => { form.resetFields(); form.setFieldsValue({ type: 'SELF', priority: 100 }); setOpen(true); }}>新建仓库</Button>
          </PermissionGate>
        }
      />
      <DataTable<Warehouse>
        rowKey="id"
        columns={columns}
        data={query.data?.items ?? []}
        loading={query.isLoading}
        error={query.error}
        onRetry={() => void query.refetch()}
        showPagination={false}
        emptyTitle="暂无仓库"
      />
      <Modal
        open={open}
        title="新建仓库"
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
            <Form.Item label="仓库编码" name="code" rules={[{ required: true, message: '请输入仓库编码' }]}>
              <Input style={{ width: 180 }} placeholder="如：WH-HZ-01" />
            </Form.Item>
            <Form.Item label="仓库名称" name="name" rules={[{ required: true, message: '请输入仓库名称' }]}>
              <Input style={{ width: 180 }} placeholder="如：杭州自营仓" />
            </Form.Item>
            <Form.Item label="类型" name="type">
              <Select style={{ width: 140 }} options={WAREHOUSE_TYPES.map((value) => ({ value, label: WAREHOUSE_TYPE_LABELS[value] }))} />
            </Form.Item>
            <Form.Item label="优先级" name="priority">
              <InputNumber min={0} style={{ width: 120 }} />
            </Form.Item>
          </Space>
          <Form.Item label="区域" name="region">
            <Input placeholder="如：华东" />
          </Form.Item>
          <Form.Item label="地址" name="address">
            <Input placeholder="详细地址" />
          </Form.Item>
          <Space size={12} wrap>
            <Form.Item label="联系人" name="contact_name">
              <Input style={{ width: 180 }} />
            </Form.Item>
            <Form.Item label="联系电话" name="contact_mobile" rules={[{ pattern: /^1[3-9]\d{9}$/, message: '11 位手机号' }]}>
              <Input style={{ width: 180 }} maxLength={11} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </div>
  );
}
