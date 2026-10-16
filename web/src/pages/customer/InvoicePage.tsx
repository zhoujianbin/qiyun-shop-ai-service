import App from 'antd/es/app';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import Modal from 'antd/es/modal';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Table from 'antd/es/table';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { invoicesApi } from '@/api/endpoints/invoices';
import { ordersApi } from '@/api/endpoints/orders';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { PageHeader } from '@/components/common/PageHeader';
import { StatusTag } from '@/components/common/StatusTag';
import { MoneyText } from '@/components/common/MoneyText';
import { ErrorState } from '@/components/common/ErrorState';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { useAuthStore } from '@/stores/authStore';
import { errorMessage } from '@/api/errors';
import { formatDateTime } from '@/utils/datetime';
import { INVOICE_TYPE_LABELS, INVOICE_TYPE_OPTIONS } from '@/constants/productStatus';
import type { Invoice, InvoiceCreateRequest, InvoiceType } from '@/types/domain';

interface InvoiceFormValues {
  order_id: number;
  type: InvoiceType;
  title: string;
  tax_no?: string;
  email?: string;
  remark?: string;
}

/** C 端发票：可开票订单、开票申请与发票列表。 */
export default function InvoicePage() {
  const { message } = App.useApp();
  const user = useAuthStore((state) => state.user);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm<InvoiceFormValues>();
  const invoiceType = Form.useWatch('type', form) ?? 'VAT_NORMAL';

  const query = useQuery({
    queryKey: queryKeys.invoices.list({ customer_id: user?.id, page: 1, page_size: 20 }),
    queryFn: ({ signal }) => invoicesApi.list({ customer_id: user?.id, page: 1, page_size: 20, signal }),
    enabled: Boolean(user?.id),
  });

  const ordersQuery = useQuery({
    queryKey: queryKeys.orders.list({ customer_id: user?.id, status: 'COMPLETED', page: 1, page_size: 50 }),
    queryFn: ({ signal }) => ordersApi.list({ customer_id: user?.id, status: 'COMPLETED', page: 1, page_size: 50, signal }),
    enabled: Boolean(user?.id) && open,
  });

  const createMutation = useIdempotentMutation(
    (vars: InvoiceCreateRequest) => invoicesApi.create(vars),
    {
      onSuccess: async () => {
        message.success('开票申请已提交');
        setOpen(false);
        createMutation.resetKey();
        await queryClient.invalidateQueries({ queryKey: ['invoices'] });
      },
      onError: (error) => message.error(errorMessage(error)),
    },
  );

  const columns: ColumnsType<Invoice> = [
    { title: '发票抬头', dataIndex: 'title', key: 'title' },
    { title: '类型', dataIndex: 'type', key: 'type', render: (value: InvoiceType) => INVOICE_TYPE_LABELS[value] ?? value },
    { title: '发票号码', dataIndex: 'invoice_no', key: 'invoice_no', render: (value?: string) => value ?? '-' },
    { title: '金额', dataIndex: 'amount', key: 'amount', render: (value?: string) => <MoneyText value={value} /> },
    { title: '状态', dataIndex: 'status', key: 'status', render: (value: string) => <StatusTag kind="invoice" value={value} /> },
    { title: '开票时间', dataIndex: 'issued_at', key: 'issued_at', render: (value?: string) => formatDateTime(value) },
  ];

  return (
    <div className="qy-page" style={{ maxWidth: 1000, margin: '0 auto' }}>
      <PageHeader
        title="发票"
        subtitle="为已完成订单申请开票，支持电子普票与增值税专票"
        extra={<Button type="primary" onClick={() => setOpen(true)}>申请开票</Button>}
      />
      {query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <Table<Invoice>
          rowKey="id"
          columns={columns}
          dataSource={query.data?.items ?? []}
          loading={query.isLoading}
          locale={{ emptyText: '暂无可开票订单或发票记录' }}
          pagination={false}
        />
      )}

      <Modal
        open={open}
        title="申请开票"
        okText="提交申请"
        cancelText="取消"
        confirmLoading={createMutation.isPending}
        onCancel={() => setOpen(false)}
        onOk={() => {
          void form.validateFields().then((values) => {
            createMutation.mutate({
              order_id: values.order_id,
              type: values.type,
              title: values.title,
              tax_no: values.tax_no ?? null,
              email: values.email ?? null,
              remark: values.remark ?? null,
            });
          });
        }}
        destroyOnClose
      >
        <Form form={form} layout="vertical" initialValues={{ type: 'ELECTRONIC' }}>
          <Form.Item label="可开票订单" name="order_id" rules={[{ required: true, message: '请选择订单' }]}>
            <Select
              showSearch
              optionFilterProp="label"
              placeholder="仅显示已完成订单"
              loading={ordersQuery.isLoading}
              options={(ordersQuery.data?.items ?? []).map((order) => ({ value: order.id, label: `${order.order_no} · 实付 ${order.paid_amount ?? order.payable_amount}` }))}
            />
          </Form.Item>
          <Form.Item label="发票类型" name="type" rules={[{ required: true, message: '请选择发票类型' }]}>
            <Select options={INVOICE_TYPE_OPTIONS} onChange={() => form.setFieldValue('tax_no', form.getFieldValue('tax_no'))} />
          </Form.Item>
          <Form.Item label="发票抬头" name="title" rules={[{ required: true, message: '请输入发票抬头' }, { max: 128, message: '不超过 128 字' }]}>
            <Input placeholder={invoiceType === 'VAT_SPECIAL' ? '企业名称' : '个人姓名 / 企业名称'} />
          </Form.Item>
          <Form.Item
            label="纳税人识别号"
            name="tax_no"
            rules={[
              { required: invoiceType === 'VAT_SPECIAL', message: '专用发票必须填写税号' },
              { pattern: /^[A-Za-z0-9]{15,20}$/, message: '税号 15–20 位字母数字' },
            ]}
          >
            <Input placeholder="企业税号" maxLength={20} />
          </Form.Item>
          <Form.Item label="接收邮箱" name="email" rules={[{ type: 'email', message: '邮箱格式不正确' }]}>
            <Input placeholder="电子发票接收邮箱" />
          </Form.Item>
          <Form.Item label="备注" name="remark" rules={[{ max: 200, message: '不超过 200 字' }]}>
            <Input.TextArea rows={2} maxLength={200} showCount />
          </Form.Item>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            专票需提供税号、开户行与注册地址；提交后由财务审核开具。
          </Typography.Text>
        </Form>
      </Modal>
    </div>
  );
}
