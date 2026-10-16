import App from 'antd/es/app';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Descriptions from 'antd/es/descriptions';
import Drawer from 'antd/es/drawer';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Table from 'antd/es/table';
import Tag from 'antd/es/tag';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { refundsApi } from '@/api/endpoints/refunds';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { DataTable } from '@/components/data/DataTable';
import { FilterBar } from '@/components/data/FilterBar';
import { PageHeader } from '@/components/common/PageHeader';
import { PermissionGate } from '@/components/common/PermissionGate';
import { StatusTag } from '@/components/common/StatusTag';
import { MoneyText } from '@/components/common/MoneyText';
import { ErrorState } from '@/components/common/ErrorState';
import { useUrlFilters } from '@/hooks/useUrlFilters';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { usePermission } from '@/hooks/usePermission';
import { errorMessage } from '@/api/errors';
import { formatDateTime } from '@/utils/datetime';
import { isValidMoney } from '@/utils/money';
import { REFUND_STATUS_OPTIONS } from '@/constants/statusMaps';
import { P } from '@/types/permissions';
import type { Refund, RefundAttempt } from '@/types/domain';

interface RefundFilters extends Record<string, string | undefined> {
  status?: string;
  order_id?: string;
}

/** B 端退款审核：待审队列 + 详情抽屉 + 执行退款（不可逆）。 */
export default function RefundReviewPage() {
  const { message } = App.useApp();
  const canApprove = usePermission(P.aftersalesReview);
  const url = useUrlFilters<RefundFilters>({ status: undefined, order_id: undefined });
  const [active, setActive] = useState<Refund | null>(null);
  const [amount, setAmount] = useState('');
  const [remark, setRemark] = useState('');

  const params = {
    status: url.filters.status,
    order_id: url.filters.order_id,
    page: url.page,
    page_size: url.pageSize,
  };

  const query = useQuery({
    queryKey: queryKeys.refunds.list(params),
    queryFn: ({ signal }) => refundsApi.list({ ...params, signal }),
  });

  const attemptsQuery = useQuery({
    queryKey: queryKeys.refunds.attempts(active?.id ?? ''),
    queryFn: ({ signal }) => refundsApi.attempts(active!.id, { signal }),
    enabled: Boolean(active?.id),
  });

  const executeMutation = useIdempotentMutation((id: number) => refundsApi.execute(id), {
    onSuccess: async () => {
      message.success('退款已执行');
      executeMutation.resetKey();
      await queryClient.invalidateQueries({ queryKey: ['refunds'] });
    },
    onError: (error) => message.error(errorMessage(error)),
  });

  const columns: ColumnsType<Refund> = [
    { title: '退款单号', dataIndex: 'refund_no', key: 'refund_no', render: (value: string, record) => <a onClick={() => { setActive(record); setAmount(record.amount); setRemark(record.reason ?? ''); }}>{value}</a> },
    { title: '订单 ID', dataIndex: 'order_id', key: 'order_id' },
    { title: '金额', dataIndex: 'amount', key: 'amount', render: (value: string) => <MoneyText value={value} strong /> },
    { title: '状态', dataIndex: 'status', key: 'status', render: (value: string) => <StatusTag kind="refund" value={value} /> },
    { title: '渠道', dataIndex: 'channel', key: 'channel', render: (value?: string) => value ?? '原路退回' },
    { title: '原因', dataIndex: 'reason', key: 'reason', render: (value?: string) => value ?? '-' },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: (value?: string) => formatDateTime(value) },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_, record) => (
        <PermissionGate permission={P.aftersalesReview} mode="disable" fallbackReason="需要退款审核权限">
          <Button type="link" disabled={record.status === 'SUCCESS' || record.status === 'CANCELLED'} onClick={() => { setActive(record); setAmount(record.amount); setRemark(record.reason ?? ''); }}>
            详情 / 执行
          </Button>
        </PermissionGate>
      ),
    },
  ];

  const attemptColumns: ColumnsType<RefundAttempt> = [
    { title: '第几次', dataIndex: 'attempt_no', key: 'attempt_no' },
    { title: '状态', dataIndex: 'status', key: 'status' },
    { title: '渠道', dataIndex: 'channel', key: 'channel' },
    { title: '错误信息', dataIndex: 'error_message', key: 'error_message', render: (value?: string) => value ?? '-' },
    { title: '时间', dataIndex: 'attempted_at', key: 'attempted_at', render: (value: string) => formatDateTime(value) },
  ];

  return (
    <div className="qy-page">
      <PageHeader title="退款审核" subtitle="退款单队列与执行；退款原路退回且不可逆" />
      <FilterBar onReset={() => url.reset()}>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">退款状态</span>
          <Select allowClear style={{ width: 160 }} placeholder="全部" value={url.filters.status} options={REFUND_STATUS_OPTIONS} onChange={(value) => url.setFilter('status', value)} />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">订单 ID</span>
          <Input.Search allowClear style={{ width: 160 }} placeholder="精确" defaultValue={url.filters.order_id} onSearch={(value) => url.setFilter('order_id', value || undefined)} />
        </Space>
      </FilterBar>
      <DataTable<Refund>
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
        emptyTitle="暂无退款单"
        emptyDescription="订单发起退款后会进入该队列"
      />

      <Drawer
        open={Boolean(active)}
        width={620}
        title={active ? `退款单 ${active.refund_no}` : '退款单'}
        onClose={() => setActive(null)}
        extra={
          <PermissionGate permission={P.aftersalesReview} mode="disable" fallbackReason="需要退款审核权限">
            <Button
              type="primary"
              danger
              disabled={!active || active.status === 'SUCCESS'}
              loading={executeMutation.isPending}
              onClick={() => {
                if (!active) return;
                if (amount && !isValidMoney(amount)) { message.error('退款金额格式不正确'); return; }
                executeMutation.mutate(active.id);
              }}
            >
              执行退款
            </Button>
          </PermissionGate>
        }
      >
        {active ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="关联订单">{active.order_id}</Descriptions.Item>
              <Descriptions.Item label="退款金额"><MoneyText value={active.amount} strong /></Descriptions.Item>
              <Descriptions.Item label="状态"><StatusTag kind="refund" value={active.status} /></Descriptions.Item>
              <Descriptions.Item label="渠道">{active.channel ?? '原路退回'}</Descriptions.Item>
              <Descriptions.Item label="执行时间">{formatDateTime(active.executed_at)}</Descriptions.Item>
            </Descriptions>
            <Card size="small" title="审核信息">
              <Space direction="vertical" style={{ width: '100%' }}>
                {!canApprove ? <Tag color="warning">当前账号无退款审核权限，仅可查看</Tag> : null}
                <Input value={amount} onChange={(event) => setAmount(event.target.value)} addonBefore="金额" placeholder="0.00" />
                <Input.TextArea rows={2} maxLength={200} value={remark} onChange={(event) => setRemark(event.target.value)} placeholder="退款说明 / 驳回原因" />
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  并发保护：执行时携带退款单版本；若已被处理将提示并刷新。
                </Typography.Text>
              </Space>
            </Card>
            <Card size="small" title="退款尝试记录">
              {attemptsQuery.isError ? (
                <ErrorState error={attemptsQuery.error} onRetry={() => void attemptsQuery.refetch()} compact />
              ) : (
                <Table<RefundAttempt> rowKey="id" size="small" columns={attemptColumns} dataSource={attemptsQuery.data?.items ?? []} loading={attemptsQuery.isLoading} pagination={false} />
              )}
            </Card>
          </Space>
        ) : null}
      </Drawer>
    </div>
  );
}
