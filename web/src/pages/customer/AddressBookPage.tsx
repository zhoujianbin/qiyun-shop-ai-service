import App from 'antd/es/app';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Form from 'antd/es/form';
import Modal from 'antd/es/modal';
import Popconfirm from 'antd/es/popconfirm';
import Space from 'antd/es/space';
import Table from 'antd/es/table';
import Tag from 'antd/es/tag';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { customersApi } from '@/api/endpoints/customers';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { PageHeader } from '@/components/common/PageHeader';
import { AddressForm } from '@/components/form/AddressForm';
import { ErrorState } from '@/components/common/ErrorState';
import { MaskedText } from '@/components/common/MaskedText';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { useAuthStore } from '@/stores/authStore';
import { errorMessage } from '@/api/errors';
import { ROUTES } from '@/constants/routes';
import type { CustomerAddress, CustomerAddressRequest } from '@/types/domain';

const MAX_ADDRESSES = 20;

/** C 端地址管理：新增/编辑/删除/设为默认；收件人手机必填 11 位。 */
export default function AddressBookPage() {
  const { message } = App.useApp();
  const user = useAuthStore((state) => state.user);
  const customerId = user?.id;
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<CustomerAddress | null>(null);
  const [form] = Form.useForm<CustomerAddressRequest>();

  const query = useQuery({
    queryKey: queryKeys.customers.addresses(customerId ?? 0),
    queryFn: ({ signal }) => customersApi.myAddresses(),
    enabled: Boolean(customerId),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['customers'] });

  const saveMutation = useIdempotentMutation(
    (vars: { id?: number; body: CustomerAddressRequest }) =>
      vars.id ? customersApi.updateMyAddress(vars.id, vars.body) : customersApi.createMyAddress(vars.body),
    {
      onSuccess: async () => {
        message.success('地址已保存');
        setOpen(false);
        saveMutation.resetKey();
        await invalidate();
      },
      onError: (error) => message.error(errorMessage(error)),
    },
  );

  const removeMutation = useIdempotentMutation((id: number) => customersApi.deleteMyAddress(id), {
    onSuccess: async () => { message.success('地址已删除'); removeMutation.resetKey(); await invalidate(); },
    onError: (error) => message.error(errorMessage(error)),
  });

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ is_default: false } as CustomerAddressRequest);
    setOpen(true);
  };

  const openEdit = (record: CustomerAddress) => {
    setEditing(record);
    form.setFieldsValue({
      receiver_name: record.receiver_name,
      receiver_mobile: record.receiver_mobile_masked ?? '',
      province: record.province,
      city: record.city,
      district: record.district,
      detail: record.detail,
      postal_code: record.postal_code ?? undefined,
      is_default: record.is_default,
    });
    setOpen(true);
  };

  const columns: ColumnsType<CustomerAddress> = [
    {
      title: '收件人',
      key: 'receiver',
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Space size={6}>
            <Typography.Text strong>{record.receiver_name}</Typography.Text>
            {record.is_default ? <Tag color="success">默认</Tag> : null}
          </Space>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            <MaskedText value={record.receiver_mobile_masked} />
          </Typography.Text>
        </Space>
      ),
    },
    {
      title: '地址',
      key: 'address',
      render: (_, record) => `${record.province}${record.city}${record.district}${record.detail}`,
    },
    { title: '邮编', dataIndex: 'postal_code', key: 'postal_code', render: (value?: string) => value ?? '-' },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_, record) => (
        <Space>
          <Button type="link" onClick={() => openEdit(record)}>编辑</Button>
          <Popconfirm title="确认删除该地址？" onConfirm={() => removeMutation.mutate(record.id)} okText="删除" cancelText="取消">
            <Button type="link" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const addresses = query.data ?? [];

  return (
    <div className="qy-page" style={{ maxWidth: 900, margin: '0 auto' }}>
      <PageHeader
        title="地址管理"
        subtitle={`最多可保存 ${MAX_ADDRESSES} 个收货地址`}
        breadcrumb={[{ label: '个人中心', to: ROUTES.account }, { label: '地址管理' }]}
        extra={<Button type="primary" disabled={addresses.length >= MAX_ADDRESSES} onClick={openCreate}>新增地址</Button>}
      />
      {query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <Card>
          <Table<CustomerAddress>
            rowKey="id"
            columns={columns}
            dataSource={addresses}
            loading={query.isLoading}
            pagination={false}
            locale={{ emptyText: '还没有收货地址，点击右上角新增' }}
          />
        </Card>
      )}

      <Modal
        open={open}
        title={editing ? '编辑地址' : '新增地址'}
        okText="保存"
        cancelText="取消"
        width={640}
        confirmLoading={saveMutation.isPending}
        onCancel={() => setOpen(false)}
        onOk={() => {
          void form.validateFields().then((values) => {
            saveMutation.mutate({ id: editing?.id, body: values });
          });
        }}
        destroyOnClose
      >
        <AddressForm form={form} />
      </Modal>
    </div>
  );
}
