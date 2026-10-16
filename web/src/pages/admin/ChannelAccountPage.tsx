import App from 'antd/es/app';
import Button from 'antd/es/button';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import Modal from 'antd/es/modal';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Switch from 'antd/es/switch';
import Tag from 'antd/es/tag';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { channelsApi } from '@/api/endpoints/channels';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { DataTable } from '@/components/data/DataTable';
import { PageHeader } from '@/components/common/PageHeader';
import { PermissionGate } from '@/components/common/PermissionGate';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { errorMessage } from '@/api/errors';
import { CHANNEL_TYPE_LABELS, CHANNEL_TYPE_OPTIONS } from '@/constants/channel';
import { P } from '@/types/permissions';
import type { ChannelAccount, ChannelAccountCreateRequest, ChannelType } from '@/types/domain';

interface ChannelFormValues {
  code: string;
  name: string;
  platform_code: string;
  channel_type: ChannelType;
  external_account_id?: string;
  commerce_enabled?: boolean;
  status?: 'ACTIVE' | 'DISABLED';
}

/** B 端渠道账号：官方商城 / 旗舰店 / 授权门店。 */
export default function ChannelAccountPage() {
  const { message } = App.useApp();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ChannelAccount | null>(null);
  const [form] = Form.useForm<ChannelFormValues>();

  const query = useQuery({
    queryKey: queryKeys.channels.list({ page: 1, page_size: 100 }),
    queryFn: ({ signal }) => channelsApi.list({ page: 1, page_size: 100, signal }),
  });

  const saveMutation = useIdempotentMutation(
    (vars: { id?: number; values: ChannelFormValues }) =>
      vars.id
        ? channelsApi.update(vars.id, { name: vars.values.name, external_account_id: vars.values.external_account_id ?? null, commerce_enabled: vars.values.commerce_enabled, status: vars.values.status })
        : channelsApi.create(vars.values as ChannelAccountCreateRequest),
    {
      onSuccess: async () => { message.success('渠道账号已保存'); setOpen(false); saveMutation.resetKey(); await queryClient.invalidateQueries({ queryKey: ['channels'] }); },
      onError: (error) => message.error(errorMessage(error)),
    },
  );

  const columns: ColumnsType<ChannelAccount> = [
    { title: '渠道名称', dataIndex: 'name', key: 'name' },
    { title: '编码', dataIndex: 'code', key: 'code' },
    { title: '类型', dataIndex: 'channel_type', key: 'channel_type', render: (value: ChannelType) => <Tag color="blue">{CHANNEL_TYPE_LABELS[value] ?? value}</Tag> },
    { title: '平台', dataIndex: 'platform_code', key: 'platform_code', render: (value?: string) => value ?? '-' },
    { title: '外部账号', dataIndex: 'external_account_id', key: 'external_account_id', render: (value?: string) => value ?? '-' },
    { title: '交易能力', dataIndex: 'commerce_enabled', key: 'commerce_enabled', render: (value?: boolean) => (value ? <Tag color="success">已开启</Tag> : <Tag>未开启</Tag>) },
    { title: '状态', dataIndex: 'status', key: 'status', render: (value: string) => (value === 'ACTIVE' ? <Tag color="success">启用</Tag> : <Tag>停用</Tag>) },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, record) => (
        <PermissionGate permission={P.staffWrite} mode="disable" fallbackReason="需要组织写权限">
          <Button type="link" onClick={() => { setEditing(record); form.setFieldsValue({ code: record.code, name: record.name, platform_code: record.platform_code ?? '', channel_type: record.channel_type, external_account_id: record.external_account_id ?? undefined, commerce_enabled: record.commerce_enabled, status: record.status }); setOpen(true); }}>编辑</Button>
        </PermissionGate>
      ),
    },
  ];

  return (
    <div className="qy-page">
      <PageHeader
        title="渠道账号"
        subtitle="渠道隔离的数据范围来源"
        extra={
          <PermissionGate permission={P.staffWrite} mode="disable" fallbackReason="需要组织写权限">
            <Button type="primary" onClick={() => { setEditing(null); form.resetFields(); form.setFieldsValue({ channel_type: 'OFFICIAL_MALL', commerce_enabled: true, platform_code: 'SELF_MALL' }); setOpen(true); }}>新建渠道账号</Button>
          </PermissionGate>
        }
      />
      <DataTable<ChannelAccount>
        rowKey="id"
        columns={columns}
        data={query.data?.items ?? []}
        loading={query.isLoading}
        error={query.error}
        onRetry={() => void query.refetch()}
        showPagination={false}
        emptyTitle="暂无渠道账号"
      />
      <Modal
        open={open}
        title={editing ? `编辑渠道：${editing.name}` : '新建渠道账号'}
        okText="保存"
        cancelText="取消"
        confirmLoading={saveMutation.isPending}
        onCancel={() => setOpen(false)}
        onOk={() => { void form.validateFields().then((values) => saveMutation.mutate({ id: editing?.id, values })); }}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Space size={12} wrap>
            <Form.Item label="渠道编码" name="code" rules={[{ required: true, message: '请输入渠道编码' }]}>
              <Input style={{ width: 200 }} disabled={Boolean(editing)} placeholder="如：MALL_OFFICIAL" />
            </Form.Item>
            <Form.Item label="渠道名称" name="name" rules={[{ required: true, message: '请输入渠道名称' }]}>
              <Input style={{ width: 200 }} placeholder="如：官方商城" />
            </Form.Item>
          </Space>
          <Space size={12} wrap>
            <Form.Item label="渠道类型" name="channel_type" rules={[{ required: true, message: '请选择渠道类型' }]}>
              <Select style={{ width: 200 }} options={CHANNEL_TYPE_OPTIONS} disabled={Boolean(editing)} />
            </Form.Item>
            <Form.Item label="平台编码" name="platform_code" rules={[{ required: true, message: '请输入平台编码' }]}>
              <Input style={{ width: 180 }} disabled={Boolean(editing)} placeholder="SELF_MALL / TMALL / JD" />
            </Form.Item>
          </Space>
          <Form.Item label="外部账号 ID" name="external_account_id">
            <Input placeholder="选填，电商平台店铺或门店标识" />
          </Form.Item>
          <Form.Item label="开启交易能力" name="commerce_enabled" valuePropName="checked">
            <Switch />
          </Form.Item>
          {editing ? (
            <Form.Item label="状态" name="status">
              <Select options={[{ value: 'ACTIVE', label: '启用' }, { value: 'DISABLED', label: '停用' }]} />
            </Form.Item>
          ) : null}
        </Form>
      </Modal>
    </div>
  );
}
