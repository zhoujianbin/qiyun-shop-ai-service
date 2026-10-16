import App from 'antd/es/app';
import Button from 'antd/es/button';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import InputNumber from 'antd/es/input-number';
import Modal from 'antd/es/modal';
import Space from 'antd/es/space';
import Select from 'antd/es/select';
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
import type { Category, CategoryCreateRequest, CategoryUpdateRequest } from '@/types/domain';

interface CategoryFormValues {
  parent_id?: number;
  code: string;
  name: string;
  icon_url?: string;
  sort_order?: number;
  status?: 'ACTIVE' | 'DISABLED';
}

/** B 端类目管理：分类树维护，支持父子层级。 */
export default function CategoryPage() {
  const { message } = App.useApp();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Category | null>(null);
  const [form] = Form.useForm<CategoryFormValues>();

  const query = useQuery({
    queryKey: queryKeys.catalog.categories(),
    queryFn: ({ signal }) => catalogApi.categories({ signal }),
  });

  const saveMutation = useIdempotentMutation(
    (vars: { id?: number; body: CategoryCreateRequest | CategoryUpdateRequest }) =>
      vars.id ? catalogApi.updateCategory(vars.body as CategoryUpdateRequest) : catalogApi.createCategory(vars.body as CategoryCreateRequest),
    {
      onSuccess: async () => {
        message.success('类目已保存');
        setOpen(false);
        saveMutation.resetKey();
        await queryClient.invalidateQueries({ queryKey: ['catalog'] });
      },
      onError: (error) => message.error(errorMessage(error)),
    },
  );

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ sort_order: 0, status: 'ACTIVE' });
    setOpen(true);
  };

  const openEdit = (record: Category) => {
    setEditing(record);
    form.setFieldsValue({
      parent_id: record.parent_id ?? undefined,
      code: record.code,
      name: record.name,
      icon_url: record.icon_url ?? undefined,
      sort_order: record.sort_order ?? 0,
      status: record.status,
    });
    setOpen(true);
  };

  const columns: ColumnsType<Category> = [
    { title: '类目名称', dataIndex: 'name', key: 'name' },
    { title: '编码', dataIndex: 'code', key: 'code' },
    { title: '层级', dataIndex: 'depth', key: 'depth', width: 80 },
    { title: '排序', dataIndex: 'sort_order', key: 'sort_order', width: 80 },
    { title: '状态', dataIndex: 'status', key: 'status', width: 100, render: (value: string) => <StatusTag kind="product" value={value === 'ACTIVE' ? 'ON_SALE' : 'OFF_SHELF'} /> },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_, record) => (
        <PermissionGate permission={P.productWrite} mode="disable" fallbackReason="需要商品写权限">
          <Button type="link" onClick={() => openEdit(record)}>编辑</Button>
        </PermissionGate>
      ),
    },
  ];

  return (
    <div className="qy-page">
      <PageHeader
        title="类目管理"
        subtitle="产品线分类树，支持最多 5 级"
        extra={
          <PermissionGate permission={P.productWrite} mode="disable" fallbackReason="需要商品写权限">
            <Button type="primary" onClick={openCreate}>新建类目</Button>
          </PermissionGate>
        }
      />
      <DataTable<Category>
        rowKey="id"
        columns={columns}
        data={query.data ?? []}
        loading={query.isLoading}
        error={query.error}
        onRetry={() => void query.refetch()}
        showPagination={false}
        emptyTitle="暂无类目"
        emptyAction={<Button type="primary" onClick={openCreate}>新建类目</Button>}
      />

      <Modal
        open={open}
        title={editing ? `编辑类目：${editing.name}` : '新建类目'}
        okText="保存"
        cancelText="取消"
        confirmLoading={saveMutation.isPending}
        onCancel={() => setOpen(false)}
        onOk={() => {
          void form.validateFields().then((values) => {
            if (editing) {
              saveMutation.mutate({ id: editing.id, body: { id: editing.id, ...values } });
            } else {
              saveMutation.mutate({ body: values });
            }
          });
        }}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item label="上级类目" name="parent_id">
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              placeholder="不选则为根类目"
              options={(query.data ?? []).filter((item) => item.id !== editing?.id).map((item) => ({ value: item.id, label: item.name }))}
            />
          </Form.Item>
          <Space size={12} wrap>
            <Form.Item label="类目编码" name="code" rules={[{ required: true, message: '请输入编码' }]}>
              <Input style={{ width: 200 }} placeholder="如：SMART_LOCK" />
            </Form.Item>
            <Form.Item label="类目名称" name="name" rules={[{ required: true, message: '请输入名称' }]}>
              <Input style={{ width: 200 }} placeholder="如：智能门锁" />
            </Form.Item>
            <Form.Item label="排序" name="sort_order">
              <InputNumber min={0} style={{ width: 120 }} />
            </Form.Item>
            <Form.Item label="状态" name="status">
              <Select style={{ width: 120 }} options={[{ value: 'ACTIVE', label: '启用' }, { value: 'DISABLED', label: '停用' }]} />
            </Form.Item>
          </Space>
          <Form.Item label="图标地址" name="icon_url">
            <Input placeholder="选填，对象存储 URL" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
