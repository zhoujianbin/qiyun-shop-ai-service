import App from 'antd/es/app';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Col from 'antd/es/col';
import Descriptions from 'antd/es/descriptions';
import Input from 'antd/es/input';
import Row from 'antd/es/row';
import Space from 'antd/es/space';
import Table from 'antd/es/table';
import Tag from 'antd/es/tag';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { customersApi } from '@/api/endpoints/customers';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { PageHeader } from '@/components/common/PageHeader';
import { ErrorState } from '@/components/common/ErrorState';
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton';
import { MaskedText } from '@/components/common/MaskedText';
import { MoneyText } from '@/components/common/MoneyText';
import { StatusTag } from '@/components/common/StatusTag';
import { PermissionGate } from '@/components/common/PermissionGate';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { errorMessage } from '@/api/errors';
import { formatDate, formatDateTime } from '@/utils/datetime';
import { P } from '@/types/permissions';
import type { CustomerAddress, Order } from '@/types/domain';

/** B 端客户档案：基本信息 + 地址簿（只读脱敏）+ 订单记录 + 备注。 */
export default function CustomerProfilePage() {
  const { customerId } = useParams();
  const id = Number(customerId);
  const { message } = App.useApp();
  const [remark, setRemark] = useState<string | null>(null);

  const query = useQuery({
    queryKey: queryKeys.customers.detail(id),
    queryFn: ({ signal }) => customersApi.detail(id),
    enabled: Number.isFinite(id),
  });
  const addressQuery = useQuery({
    queryKey: queryKeys.customers.addresses(id),
    queryFn: () => customersApi.addresses(id),
    enabled: Number.isFinite(id),
  });
  const orderQuery = useQuery({
    queryKey: queryKeys.customers.orders(id, { page: 1, page_size: 20 }),
    queryFn: ({ signal }) => customersApi.orders(id, { page: 1, page_size: 20, signal }),
    enabled: Number.isFinite(id),
  });

  const noteMutation = useIdempotentMutation((vars: { id: number; remark: string }) => customersApi.update(id, { remark: vars.remark }), {
    onSuccess: async () => { message.success('备注已保存'); noteMutation.resetKey(); await queryClient.invalidateQueries({ queryKey: ['customers'] }); },
    onError: (error) => message.error(errorMessage(error)),
  });

  const customer = query.data;

  if (query.isLoading) return <div className="qy-page"><LoadingSkeleton rows={8} /></div>;
  if (query.isError || !customer) {
    return <div className="qy-page"><ErrorState title="客户档案加载失败" error={query.error} onRetry={() => void query.refetch()} /></div>;
  }

  const addressColumns: ColumnsType<CustomerAddress> = [
    { title: '收件人', dataIndex: 'receiver_name', key: 'receiver_name' },
    { title: '手机号', dataIndex: 'receiver_mobile_masked', key: 'receiver_mobile_masked', render: (value?: string) => <MaskedText value={value} /> },
    { title: '地址', key: 'address', render: (_, record) => `${record.province}${record.city}${record.district}${record.detail}` },
    { title: '默认', dataIndex: 'is_default', key: 'is_default', render: (value?: boolean) => (value ? <Tag color="success">默认</Tag> : '-') },
  ];

  const orderColumns: ColumnsType<Order> = [
    { title: '订单号', dataIndex: 'order_no', key: 'order_no' },
    { title: '应付', dataIndex: 'payable_amount', key: 'payable_amount', render: (value: string) => <MoneyText value={value} /> },
    { title: '状态', dataIndex: 'status', key: 'status', render: (value: string) => <StatusTag kind="order" value={value} /> },
    { title: '履约', dataIndex: 'fulfillment_status', key: 'fulfillment_status', render: (value: string) => <StatusTag kind="fulfillment" value={value} /> },
    { title: '售后', dataIndex: 'after_sales_status', key: 'after_sales_status', render: (value: string) => <StatusTag kind="orderAfterSales" value={value} /> },
    { title: '下单时间', dataIndex: 'created_at', key: 'created_at', render: (value: string) => formatDateTime(value) },
  ];

  return (
    <div className="qy-page">
      <PageHeader title={customer.nickname ?? customer.customer_no} subtitle={`客户编号 ${customer.customer_no}`} />
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="基本信息">
            <Descriptions column={2} size="small">
              <Descriptions.Item label="客户编号">{customer.customer_no}</Descriptions.Item>
              <Descriptions.Item label="昵称">{customer.nickname ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="姓名">{customer.real_name ?? '未提供'}</Descriptions.Item>
              <Descriptions.Item label="手机号"><MaskedText value={customer.mobile_masked} /></Descriptions.Item>
              <Descriptions.Item label="邮箱">{customer.email ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="注册时间">{formatDate(customer.created_at)}</Descriptions.Item>
              <Descriptions.Item label="订单数">{customer.total_order_count ?? 0}</Descriptions.Item>
              <Descriptions.Item label="累计消费"><MoneyText value={customer.total_paid_amount} strong /></Descriptions.Item>
              <Descriptions.Item label="状态">{customer.status === 'ACTIVE' ? '正常' : '停用'}</Descriptions.Item>
              <Descriptions.Item label="最近下单">{formatDateTime(customer.last_order_at)}</Descriptions.Item>
              <Descriptions.Item label="标签" span={2}>
                <Space wrap>{(customer.tags ?? []).length === 0 ? '-' : (customer.tags ?? []).map((tag) => <Tag key={tag}>{tag}</Tag>)}</Space>
              </Descriptions.Item>
            </Descriptions>
          </Card>
          <Card title="备注" style={{ marginTop: 16 }}>
            <Input.TextArea rows={3} maxLength={200} showCount value={remark ?? customer.remark ?? ''} onChange={(event) => setRemark(event.target.value)} disabled={!customer} />
            <div style={{ marginTop: 8 }}>
              <PermissionGate permission={P.customerWrite} mode="disable" fallbackReason="需要客户写权限">
                <Button type="primary" loading={noteMutation.isPending} onClick={() => noteMutation.mutate({ id: customer.id, remark: remark ?? customer.remark ?? '' })}>保存备注</Button>
              </PermissionGate>
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="地址簿（脱敏只读）">
            {addressQuery.isError ? (
              <ErrorState error={addressQuery.error} onRetry={() => void addressQuery.refetch()} compact />
            ) : (
              <Table<CustomerAddress> rowKey="id" size="small" columns={addressColumns} dataSource={addressQuery.data ?? []} loading={addressQuery.isLoading} pagination={false} locale={{ emptyText: '该客户暂无地址' }} />
            )}
          </Card>
          <Card title="订单与售后记录" style={{ marginTop: 16 }}>
            {orderQuery.isError ? (
              <ErrorState error={orderQuery.error} onRetry={() => void orderQuery.refetch()} compact />
            ) : (
              <Table<Order> rowKey="id" size="small" columns={orderColumns} dataSource={orderQuery.data?.items ?? []} loading={orderQuery.isLoading} pagination={false} locale={{ emptyText: '该客户暂无订单' }} scroll={{ x: 720 }} />
            )}
          </Card>
          <Card title="操作审计" style={{ marginTop: 16 }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              该客户档案的查看与修改均写入审计日志（shared.audit_log），可在审计日志页按资源类型 Customer 检索。
            </Typography.Text>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
