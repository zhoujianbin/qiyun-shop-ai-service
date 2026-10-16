import App from 'antd/es/app';
import Button from 'antd/es/button';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import Modal from 'antd/es/modal';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { invoicesApi } from '@/api/endpoints/invoices';
import { ordersApi } from '@/api/endpoints/orders';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { DataTable } from '@/components/data/DataTable';
import { FilterBar } from '@/components/data/FilterBar';
import { PageHeader } from '@/components/common/PageHeader';
import { PermissionGate } from '@/components/common/PermissionGate';
import { StatusTag } from '@/components/common/StatusTag';
import { MoneyText } from '@/components/common/MoneyText';
import { useUrlFilters } from '@/hooks/useUrlFilters';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { errorMessage } from '@/api/errors';
import { formatDateTime } from '@/utils/datetime';
import { INVOICE_STATUS_OPTIONS, INVOICE_TYPE_LABELS, INVOICE_TYPE_OPTIONS } from '@/constants/productStatus';
import { P } from '@/types/permissions';
import type { Invoice, InvoiceCreateRequest, InvoiceIssueRequest, InvoiceType } from '@/types/domain';

interface InvoiceFilters extends Record<string, string | undefined> {
  status?: string;
  order_id?: string;
}

/** B 端发票管理：开票申请、开具与作废/红冲。 */
export default function InvoicePage() {
  const { message } = App.useApp();
  const [params] = useSearchParams();
  const url = useUrlFilters<InvoiceFilters>({ status: undefined, order_id: undefined });
  const [createOpen, setCreateOpen] = useState(Boolean(params.get('order_id')));
  const [issueTarget, setIssueTarget] = useState<Invoice | null>(null);
  const [voidTarget, setVoidTarget] = useState<Invoice | null>(null);
  const [createForm] = Form.useForm<InvoiceCreateRequest>();
  const [issueForm] = Form.useForm<InvoiceIssueRequest>();
  const [voidForm] = Form.useForm<{ reason: string }>();

  const query = useQuery({
    queryKey: queryKeys.invoices.list({ ...url.filters, page: url.page, page_size: url.pageSize }),
    queryFn: ({ signal }) => invoicesApi.list({ ...url.filters, page: url.page, page_size: url.pageSize, signal }),
  });
  const ordersQuery = useQuery({
    queryKey: queryKeys.orders.list({ status: 'COMPLETED', page: 1, page_size: 50 }),
    queryFn: ({ signal }) => ordersApi.list({ status: 'COMPLETED', page: 1, page_size: 50, signal }),
    enabled: createOpen,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['invoices'] });

  const createMutation = useIdempotentMutation((body: InvoiceCreateRequest) => invoicesApi.create(body), {
    onSuccess: async () => { message.success('开票申请已创建'); setCreateOpen(false); createMutation.resetKey(); await invalidate(); },
    onError: (error) => message.error(errorMessage(error)),
  });
  const issueMutation = useIdempotentMutation((vars: { id: number; body: InvoiceIssueRequest }) => invoicesApi.issue(vars.id, vars.body), {
    onSuccess: async () => { message.success('发票已开具'); setIssueTarget(null); issueMutation.resetKey(); await invalidate(); },
    onError: (error) => message.error(errorMessage(error)),
  });
  const voidMutation = useIdempotentMutation((vars: { id: number; reason: string }) => invoicesApi.void(vars.id, { reason: vars.reason }), {
    onSuccess: async () => { message.success('发票已作废'); setVoidTarget(null); voidMutation.resetKey(); await invalidate(); },
    onError: (error) => message.error(errorMessage(error)),
  });

  const columns: ColumnsType<Invoice> = [
    { title: '抬头', dataIndex: 'title', key: 'title' },
    { title: '类型', dataIndex: 'type', key: 'type', render: (value: InvoiceType) => INVOICE_TYPE_LABELS[value] ?? value },
    { title: '发票号码', dataIndex: 'invoice_no', key: 'invoice_no', render: (value?: string) => value ?? '-' },
    { title: '订单 ID', dataIndex: 'order_id', key: 'order_id' },
    { title: '金额', dataIndex: 'amount', key: 'amount', render: (value?: string) => <MoneyText value={value} /> },
    { title: '税额', dataIndex: 'tax_amount', key: 'tax_amount', render: (value?: string) => <MoneyText value={value} muted /> },
    { title: '状态', dataIndex: 'status', key: 'status', render: (value: string) => <StatusTag kind="invoice" value={value} /> },
    { title: '开票时间', dataIndex: 'issued_at', key: 'issued_at', render: (value?: string) => formatDateTime(value) },
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_, record) => (
        <Space>
          <PermissionGate permission={P.invoiceWrite} mode="disable" fallbackReason="需要发票写权限">
            <Button type="link" disabled={record.status === 'ISSUED' || record.status === 'VOID'} onClick={() => { issueForm.setFieldsValue({ invoice_no: record.invoice_no ?? '', issue_type: 'BLUE', tax_amount: record.tax_amount ?? undefined }); setIssueTarget(record); }}>开具</Button>
          </PermissionGate>
          <PermissionGate permission={P.invoiceWrite} mode="disable" fallbackReason="需要发票写权限">
            <Button type="link" danger disabled={record.status !== 'ISSUED'} onClick={() => { voidForm.resetFields(); setVoidTarget(record); }}>作废</Button>
          </PermissionGate>
        </Space>
      ),
    },
  ];

  return (
    <div className="qy-page">
      <PageHeader
        title="发票管理"
        subtitle="开票申请、开具与红冲作废"
        extra={
          <PermissionGate permission={P.invoiceWrite} mode="disable" fallbackReason="需要发票写权限">
            <Button type="primary" onClick={() => { createForm.resetFields(); if (params.get('order_id')) createForm.setFieldsValue({ order_id: Number(params.get('order_id')), type: 'ELECTRONIC' }); setCreateOpen(true); }}>新建开票申请</Button>
          </PermissionGate>
        }
      />
      <FilterBar onReset={() => url.reset()}>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">状态</span>
          <Select allowClear style={{ width: 150 }} placeholder="全部" value={url.filters.status} options={INVOICE_STATUS_OPTIONS} onChange={(value) => url.setFilter('status', value)} />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">订单 ID</span>
          <Input.Search allowClear style={{ width: 160 }} placeholder="精确" defaultValue={url.filters.order_id} onSearch={(value) => url.setFilter('order_id', value || undefined)} />
        </Space>
      </FilterBar>
      <DataTable<Invoice>
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
        emptyTitle="暂无发票记录"
      />

      <Modal open={createOpen} title="新建开票申请" okText="提交" cancelText="取消" confirmLoading={createMutation.isPending} onCancel={() => setCreateOpen(false)} onOk={() => { void createForm.validateFields().then((values) => createMutation.mutate(values)); }} destroyOnClose>
        <Form form={createForm} layout="vertical" initialValues={{ type: 'ELECTRONIC' }}>
          <Form.Item label="订单" name="order_id" rules={[{ required: true, message: '请选择订单' }]}>
            <Select showSearch optionFilterProp="label" loading={ordersQuery.isLoading} options={(ordersQuery.data?.items ?? []).map((order) => ({ value: order.id, label: `${order.order_no} · ${order.paid_amount ?? order.payable_amount}` }))} />
          </Form.Item>
          <Form.Item label="发票类型" name="type" rules={[{ required: true, message: '请选择类型' }]}>
            <Select options={INVOICE_TYPE_OPTIONS} />
          </Form.Item>
          <Form.Item label="抬头" name="title" rules={[{ required: true, message: '请输入抬头' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="税号" name="tax_no" rules={[{ pattern: /^[A-Za-z0-9]{15,20}$/, message: '税号 15–20 位' }]}>
            <Input maxLength={20} />
          </Form.Item>
          <Form.Item label="接收邮箱" name="email" rules={[{ type: 'email', message: '邮箱格式不正确' }]}>
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <Modal open={Boolean(issueTarget)} title="开具发票" okText="确认开具" cancelText="取消" confirmLoading={issueMutation.isPending} onCancel={() => setIssueTarget(null)} onOk={() => { void issueForm.validateFields().then((values) => issueTarget && issueMutation.mutate({ id: issueTarget.id, body: values })); }} destroyOnClose>
        <Form form={issueForm} layout="vertical" initialValues={{ issue_type: 'BLUE' }}>
          <Form.Item label="发票号码" name="invoice_no" rules={[{ required: true, message: '请输入发票号码' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="发票种类" name="issue_type">
            <Select options={[{ value: 'BLUE', label: '蓝票' }, { value: 'RED', label: '红冲票' }]} />
          </Form.Item>
          <Form.Item label="税额" name="tax_amount">
            <Input placeholder="0.00" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal open={Boolean(voidTarget)} title="作废 / 红冲发票" okText="确认作废" cancelText="取消" okButtonProps={{ danger: true }} confirmLoading={voidMutation.isPending} onCancel={() => setVoidTarget(null)} onOk={() => { void voidForm.validateFields().then((values) => voidTarget && voidMutation.mutate({ id: voidTarget.id, reason: values.reason })); }} destroyOnClose>
        <Form form={voidForm} layout="vertical">
          <Form.Item label="作废原因" name="reason" rules={[{ required: true, message: '请填写作废原因' }, { max: 200, message: '不超过 200 字' }]}>
            <Input.TextArea rows={3} maxLength={200} showCount />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
