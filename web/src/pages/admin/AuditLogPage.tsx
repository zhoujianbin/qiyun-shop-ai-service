import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Descriptions from 'antd/es/descriptions';
import Drawer from 'antd/es/drawer';
import Input from 'antd/es/input';
import Radio from 'antd/es/radio';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { auditApi } from '@/api/endpoints/audit';
import { queryKeys } from '@/api/queryKeys';
import { DataTable } from '@/components/data/DataTable';
import { FilterBar } from '@/components/data/FilterBar';
import { PageHeader } from '@/components/common/PageHeader';
import { PermissionGate } from '@/components/common/PermissionGate';
import { CopyableText } from '@/components/common/CopyableText';
import { useUrlFilters } from '@/hooks/useUrlFilters';
import { usePermission } from '@/hooks/usePermission';
import { downloadCsv } from '@/utils/download';
import { formatDateTime } from '@/utils/datetime';
import { P } from '@/types/permissions';
import type { AuditLog } from '@/types/domain';

interface AuditFilters extends Record<string, string | undefined> {
  actor_type?: string;
  action?: string;
  resource_type?: string;
  resource_id?: string;
  request_id?: string;
  result?: string;
}

/** B 端审计日志：全站只读，导出写审计；详情展示 before/after。 */
export default function AuditLogPage() {
  const url = useUrlFilters<AuditFilters>({ actor_type: undefined, action: undefined, resource_type: undefined, resource_id: undefined, request_id: undefined, result: undefined });
  const [active, setActive] = useState<AuditLog | null>(null);
  const canRead = usePermission(P.auditRead);

  const params = {
    actor_type: url.filters.actor_type,
    action: url.filters.action,
    resource_type: url.filters.resource_type,
    resource_id: url.filters.resource_id,
    request_id: url.filters.request_id,
    page: url.page,
    page_size: url.pageSize,
  };

  const query = useQuery({
    queryKey: queryKeys.audit.list(params),
    queryFn: ({ signal }) => auditApi.list({ ...params, signal }),
  });

  const columns: ColumnsType<AuditLog> = [
    { title: '时间', dataIndex: 'created_at', key: 'created_at', render: (value: string) => formatDateTime(value), width: 160 },
    { title: '操作者', key: 'actor', render: (_, record) => `${record.actor_label ?? record.actor_id ?? '-'}（${record.actor_type}）` },
    { title: '动作', dataIndex: 'action', key: 'action' },
    { title: '对象类型', dataIndex: 'resource_type', key: 'resource_type' },
    { title: '对象 ID', dataIndex: 'resource_id', key: 'resource_id', render: (value?: string) => value ?? '-' },
    { title: '渠道', dataIndex: 'channel_account_id', key: 'channel_account_id', render: (value?: number) => value ?? '-' },
    { title: 'request_id', dataIndex: 'request_id', key: 'request_id', render: (value?: string) => (value ? <CopyableText value={value} label="request_id" /> : '-') },
    {
      title: '操作',
      key: 'action_view',
      width: 90,
      render: (_, record) => <Button type="link" onClick={() => setActive(record)}>详情</Button>,
    },
  ];

  return (
    <div className="qy-page">
      <PageHeader
        title="审计日志"
        subtitle="只读；时间范围默认近 7 天，导出会二次确认并写审计"
        extra={
          <PermissionGate permission={P.auditRead} mode="disable" fallbackReason="需要审计读取权限">
            <a
              onClick={() => {
                if (!window.confirm('导出将写入审计记录，确认导出当前结果？')) return;
                downloadCsv(
                  'audit_logs',
                  ['时间', '操作者', '动作', '对象类型', '对象ID', 'request_id'],
                  (query.data?.items ?? []).map((item) => [item.created_at, item.actor_label ?? String(item.actor_id ?? ''), item.action, item.resource_type, item.resource_id ?? '', item.request_id ?? '']),
                );
              }}
            >
              导出 CSV
            </a>
          </PermissionGate>
        }
      />
      <FilterBar onReset={() => url.reset()}>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">操作者类型</span>
          <Select allowClear style={{ width: 130 }} placeholder="全部" value={url.filters.actor_type} options={['STAFF', 'CUSTOMER', 'GUEST', 'SYSTEM'].map((value) => ({ value, label: value }))} onChange={(value) => url.setFilter('actor_type', value)} />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">动作</span>
          <Input.Search allowClear style={{ width: 180 }} placeholder="如 order.cancel" defaultValue={url.filters.action} onSearch={(value) => url.setFilter('action', value || undefined)} />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">对象类型</span>
          <Input.Search allowClear style={{ width: 150 }} placeholder="如 Order / Product" defaultValue={url.filters.resource_type} onSearch={(value) => url.setFilter('resource_type', value || undefined)} />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">对象 ID</span>
          <Input.Search allowClear style={{ width: 140 }} defaultValue={url.filters.resource_id} onSearch={(value) => url.setFilter('resource_id', value || undefined)} />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">request_id</span>
          <Input.Search allowClear style={{ width: 220 }} placeholder="联调定位用" defaultValue={url.filters.request_id} onSearch={(value) => url.setFilter('request_id', value || undefined)} />
        </Space>
        <Space direction="vertical" size={0}>
          <span className="qy-filter-label">结果</span>
          <Radio.Group value={url.filters.result ?? 'all'} onChange={(event) => url.setFilter('result', event.target.value === 'all' ? undefined : event.target.value)}>
            <Radio.Button value="all">全部</Radio.Button>
            <Radio.Button value="success">成功</Radio.Button>
            <Radio.Button value="fail">失败</Radio.Button>
          </Radio.Group>
        </Space>
      </FilterBar>
      {!canRead ? <Typography.Text type="warning">当前账号无审计读取权限。</Typography.Text> : null}
      <DataTable<AuditLog>
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
        emptyTitle="没有符合条件的审计记录"
        emptyDescription="可调整时间范围或清空筛选"
        scrollX={1200}
      />

      <Drawer open={Boolean(active)} width={680} title={active ? `审计详情 ${active.action}` : '审计详情'} onClose={() => setActive(null)}>
        {active ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="时间">{formatDateTime(active.created_at)}</Descriptions.Item>
              <Descriptions.Item label="操作者">{active.actor_label ?? active.actor_id ?? '-'}（{active.actor_type}）</Descriptions.Item>
              <Descriptions.Item label="对象">{active.resource_type} #{active.resource_id ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="IP / UA">{active.ip ?? '-'} / {active.user_agent ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="request_id">{active.request_id ?? '-'}</Descriptions.Item>
            </Descriptions>
            <Card size="small" title="变更前 before">
              <pre style={{ maxHeight: 240, overflow: 'auto', fontSize: 12 }}>{JSON.stringify(active.before_data ?? null, null, 2)}</pre>
            </Card>
            <Card size="small" title="变更后 after">
              <pre style={{ maxHeight: 240, overflow: 'auto', fontSize: 12 }}>{JSON.stringify(active.after_data ?? null, null, 2)}</pre>
            </Card>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>敏感字段（手机号/地址等）按后端脱敏结果展示，前端不做还原。</Typography.Text>
          </Space>
        ) : null}
      </Drawer>
    </div>
  );
}
