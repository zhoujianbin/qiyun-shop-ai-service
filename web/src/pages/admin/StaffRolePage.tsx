import App from 'antd/es/app';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Drawer from 'antd/es/drawer';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import Modal from 'antd/es/modal';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Switch from 'antd/es/switch';
import Table from 'antd/es/table';
import Tabs from 'antd/es/tabs';
import Tag from 'antd/es/tag';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { staffApi } from '@/api/endpoints/staff';
import { channelsApi } from '@/api/endpoints/channels';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { DataTable } from '@/components/data/DataTable';
import { FilterBar } from '@/components/data/FilterBar';
import { PageHeader } from '@/components/common/PageHeader';
import { PermissionGate } from '@/components/common/PermissionGate';
import { MaskedText } from '@/components/common/MaskedText';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { errorMessage } from '@/api/errors';
import { formatDateTime } from '@/utils/datetime';
import { ROLE_CODES, ROLE_LABELS, P } from '@/types/permissions';
import type { Role, StaffStatus, StaffUser, StaffUserCreateRequest, StaffUserUpdateRequest } from '@/types/domain';

interface StaffFormValues {
  username: string;
  display_name: string;
  email?: string;
  phone?: string;
  password?: string;
  role_codes: string[];
  channel_account_ids?: number[];
  status?: StaffStatus;
}

/** B 端员工与角色：员工 CRUD 与角色权限矩阵（只读展示）。 */
export default function StaffRolePage() {
  const { message } = App.useApp();
  const [keyword, setKeyword] = useState('');
  const [status, setStatus] = useState<string | undefined>();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<StaffUser | null>(null);
  const [form] = Form.useForm<StaffFormValues>();

  const query = useQuery({
    queryKey: queryKeys.staff.list({ keyword, status, page: 1, page_size: 50 }),
    queryFn: ({ signal }) => staffApi.list({ keyword, status, page: 1, page_size: 50, signal }),
  });
  const roleQuery = useQuery({
    queryKey: queryKeys.roles.list({}),
    queryFn: ({ signal }) => staffApi.roles({ signal }),
  });
  const channelQuery = useQuery({
    queryKey: queryKeys.channels.list({ page: 1, page_size: 100 }),
    queryFn: ({ signal }) => channelsApi.list({ page: 1, page_size: 100, signal }),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['staff'] });

  const saveMutation = useIdempotentMutation(
    async (vars: { id?: number; values: StaffFormValues }) => {
      if (vars.id) {
        const body: StaffUserUpdateRequest = {
          display_name: vars.values.display_name,
          email: vars.values.email ?? null,
          phone: vars.values.phone ?? null,
          status: vars.values.status,
        };
        const updated = await staffApi.update(vars.id, body);
        await staffApi.setRoles(vars.id, vars.values.role_codes ?? []);
        if (vars.values.channel_account_ids) await staffApi.setChannelScopes(vars.id, vars.values.channel_account_ids);
        return updated;
      }
      const body: StaffUserCreateRequest = {
        username: vars.values.username,
        display_name: vars.values.display_name,
        email: vars.values.email ?? null,
        phone: vars.values.phone ?? null,
        password: vars.values.password ?? '',
        role_codes: (vars.values.role_codes ?? []) as StaffUserCreateRequest['role_codes'],
        channel_account_ids: vars.values.channel_account_ids ?? [],
      };
      return staffApi.create(body);
    },
    {
      onSuccess: async () => { message.success('员工信息已保存'); setOpen(false); saveMutation.resetKey(); await invalidate(); },
      onError: (error) => message.error(errorMessage(error)),
    },
  );

  const disableMutation = useIdempotentMutation((id: number) => staffApi.disable(id), {
    onSuccess: async () => { message.success('员工已停用'); disableMutation.resetKey(); await invalidate(); },
    onError: (error) => message.error(errorMessage(error)),
  });

  const staffColumns: ColumnsType<StaffUser> = [
    { title: '姓名', dataIndex: 'display_name', key: 'display_name' },
    { title: '登录名', dataIndex: 'username', key: 'username' },
    {
      title: '角色',
      dataIndex: 'roles',
      key: 'roles',
      render: (roles?: string[]) => <Space wrap>{(roles ?? []).map((role) => <Tag key={role} color="blue">{ROLE_LABELS[role as keyof typeof ROLE_LABELS] ?? role}</Tag>)}</Space>,
    },
    {
      title: '渠道范围',
      dataIndex: 'channel_scope',
      key: 'channel_scope',
      render: (scope?: string[]) => (scope && scope.length > 0 ? scope.join(' / ') : '全部渠道'),
    },
    { title: '手机号', dataIndex: 'phone_masked', key: 'phone_masked', render: (value?: string) => <MaskedText value={value} /> },
    { title: '状态', dataIndex: 'status', key: 'status', render: (value: string) => (value === 'ACTIVE' ? <Tag color="success">启用</Tag> : <Tag>{value}</Tag>) },
    { title: '最近登录', dataIndex: 'last_login_at', key: 'last_login_at', render: (value?: string) => formatDateTime(value) },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_, record) => (
        <Space>
          <PermissionGate permission={P.staffWrite} mode="disable" fallbackReason="需要员工写权限">
            <Button type="link" onClick={() => {
              setEditing(record);
              form.setFieldsValue({
                username: record.username,
                display_name: record.display_name,
                email: record.email ?? undefined,
                phone: record.phone_masked ?? undefined,
                role_codes: (record.roles ?? []) as string[],
                status: record.status,
              });
              setOpen(true);
            }}>编辑</Button>
          </PermissionGate>
          <PermissionGate permission={P.staffWrite} mode="disable" fallbackReason="需要员工写权限">
            <Button type="link" danger disabled={record.status !== 'ACTIVE'} onClick={() => disableMutation.mutate(record.id)}>停用</Button>
          </PermissionGate>
        </Space>
      ),
    },
  ];

  const roleColumns: ColumnsType<Role> = [
    { title: '角色', dataIndex: 'name', key: 'name', render: (value: string, record) => <Space><Tag color="blue">{value}</Tag><Typography.Text type="secondary">{record.code}</Typography.Text></Space> },
    { title: '说明', dataIndex: 'description', key: 'description', render: (value?: string) => value ?? '-' },
    {
      title: '权限码',
      dataIndex: 'permissions',
      key: 'permissions',
      render: (permissions?: string[]) => (
        <Space wrap>{(permissions ?? []).slice(0, 12).map((code) => <Tag key={code}>{code}</Tag>)}{(permissions ?? []).length > 12 ? <Tag>+{(permissions ?? []).length - 12}</Tag> : null}</Space>
      ),
    },
    { title: '系统内置', dataIndex: 'is_system', key: 'is_system', width: 100, render: (value?: boolean) => (value ? '是' : '否') },
  ];

  return (
    <div className="qy-page">
      <PageHeader
        title="员工与角色"
        subtitle="账号、角色与渠道范围；权限矩阵变更写入审计"
        extra={
          <PermissionGate permission={P.staffWrite} mode="disable" fallbackReason="需要员工写权限">
            <Button type="primary" onClick={() => { setEditing(null); form.resetFields(); form.setFieldsValue({ role_codes: [], channel_account_ids: [] }); setOpen(true); }}>新建员工</Button>
          </PermissionGate>
        }
      />
      <Tabs
        items={[
          {
            key: 'staff',
            label: '员工',
            children: (
              <>
                <FilterBar onReset={() => { setKeyword(''); setStatus(undefined); }}>
                  <Space direction="vertical" size={0}>
                    <span className="qy-filter-label">关键词</span>
                    <Input.Search allowClear style={{ width: 200 }} placeholder="姓名 / 登录名" onSearch={(value) => setKeyword(value)} />
                  </Space>
                  <Space direction="vertical" size={0}>
                    <span className="qy-filter-label">状态</span>
                    <Select allowClear style={{ width: 140 }} placeholder="全部" value={status} options={[{ value: 'ACTIVE', label: '启用' }, { value: 'DISABLED', label: '停用' }, { value: 'LOCKED', label: '锁定' }, { value: 'PENDING', label: '待激活' }]} onChange={setStatus} />
                  </Space>
                </FilterBar>
                <DataTable<StaffUser>
                  rowKey="id"
                  columns={staffColumns}
                  data={query.data?.items ?? []}
                  loading={query.isLoading}
                  error={query.error}
                  onRetry={() => void query.refetch()}
                  showPagination={false}
                  emptyTitle="暂无员工"
                />
              </>
            ),
          },
          {
            key: 'roles',
            label: '角色权限矩阵',
            children: (
              <Card>
                <DataTable<Role>
                  rowKey="id"
                  columns={roleColumns}
                  data={roleQuery.data?.items ?? []}
                  loading={roleQuery.isLoading}
                  error={roleQuery.error}
                  onRetry={() => void roleQuery.refetch()}
                  showPagination={false}
                  emptyTitle="暂无角色"
                  toolbar={<Typography.Text type="secondary">一期角色为系统内置，权限码由后端定义；调整员工角色请在上方员工编辑中操作。</Typography.Text>}
                />
              </Card>
            ),
          },
        ]}
      />

      <Modal
        open={open}
        title={editing ? `编辑员工：${editing.display_name}` : '新建员工'}
        okText="保存"
        cancelText="取消"
        confirmLoading={saveMutation.isPending}
        onCancel={() => setOpen(false)}
        onOk={() => { void form.validateFields().then((values) => saveMutation.mutate({ id: editing?.id, values })); }}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Space size={12} wrap>
            <Form.Item label="登录名" name="username" rules={[{ required: true, message: '请输入登录名' }, { pattern: /^[a-z0-9._-]{4,32}$/, message: '4–32 位小写字母/数字/._-' }]}>
              <Input style={{ width: 200 }} disabled={Boolean(editing)} />
            </Form.Item>
            <Form.Item label="姓名" name="display_name" rules={[{ required: true, message: '请输入姓名' }, { min: 2, max: 32, message: '2–32 字' }]}>
              <Input style={{ width: 200 }} />
            </Form.Item>
          </Space>
          <Space size={12} wrap>
            <Form.Item label="手机号" name="phone" rules={[{ pattern: /^1[3-9]\d{9}$/, message: '11 位手机号' }]}>
              <Input style={{ width: 200 }} maxLength={11} />
            </Form.Item>
            <Form.Item label="邮箱" name="email" rules={[{ type: 'email', message: '邮箱格式不正确' }]}>
              <Input style={{ width: 220 }} />
            </Form.Item>
          </Space>
          {!editing ? (
            <Form.Item label="初始密码" name="password" rules={[{ required: true, message: '请输入初始密码' }, { min: 8, max: 64, message: '8–64 位' }, { pattern: /(?=.*[A-Za-z])(?=.*\d)/, message: '需含字母与数字' }]}>
              <Input.Password placeholder="8–64 位，含字母与数字" />
            </Form.Item>
          ) : (
            <Form.Item label="状态" name="status">
              <Select options={[{ value: 'ACTIVE', label: '启用' }, { value: 'DISABLED', label: '停用' }]} />
            </Form.Item>
          )}
          <Form.Item label="角色" name="role_codes" rules={[{ required: true, message: '请至少选择一个角色' }]}>
            <Select mode="multiple" options={ROLE_CODES.map((code) => ({ value: code, label: ROLE_LABELS[code] }))} />
          </Form.Item>
          <Form.Item label="渠道范围" name="channel_account_ids" extra="不选表示全渠道（仅管理员）">
            <Select mode="multiple" options={(channelQuery.data?.items ?? []).map((channel) => ({ value: channel.id, label: channel.name }))} />
          </Form.Item>
          <Switch disabled /> <Typography.Text type="secondary">不可停用自己</Typography.Text>
        </Form>
      </Modal>
    </div>
  );
}
