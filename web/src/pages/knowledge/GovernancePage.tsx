import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Col from 'antd/es/col';
import Row from 'antd/es/row';
import Table from 'antd/es/table';
import Tabs from 'antd/es/tabs';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { knowledgeApi } from '@/api/endpoints/knowledge';
import { queryKeys } from '@/api/queryKeys';
import { EmptyState } from '@/components/common/EmptyState';
import { ErrorState } from '@/components/common/ErrorState';
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton';
import { PageHeader } from '@/components/common/PageHeader';
import { StatCard } from '@/components/common/StatCard';
import { ROUTES } from '@/constants/routes';
import type { GovernanceItem } from '@/types/knowledge';

const CATEGORIES: Array<{ key: 'duplicate' | 'expired' | 'orphan' | 'conflict' | 'inconsistent'; label: string }> = [
  { key: 'duplicate', label: '重复' },
  { key: 'expired', label: '过期' },
  { key: 'orphan', label: '孤立' },
  { key: 'conflict', label: '冲突' },
  { key: 'inconsistent', label: '与商品不一致' },
];

/** 治理看板：五类报告 + 下钻到文档列表（带过滤条件）。 */
export default function GovernancePage() {
  const navigate = useNavigate();
  const query = useQuery({
    queryKey: queryKeys.knowledge.governance(),
    queryFn: () => knowledgeApi.governanceReport(),
  });

  if (query.isLoading) return <LoadingSkeleton rows={8} />;
  if (query.error) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  const report = query.data!;

  const drillDown = (item: GovernanceItem) => {
    const params = new URLSearchParams();
    if (item.document_id) params.set('keyword', item.document_id);
    else if (typeof item.filter.status === 'string') params.set('status', item.filter.status);
    navigate(`${ROUTES.knowledgeDocuments}?${params.toString()}`);
  };

  const columns: ColumnsType<GovernanceItem> = [
    { title: '对象', dataIndex: 'title', width: 320 },
    { title: '说明', dataIndex: 'detail' },
    {
      title: '操作',
      width: 130,
      render: (_value, row) => (
        <Button size="small" onClick={() => drillDown(row)} disabled={!row.document_id && !row.filter.status}>
          查看文档
        </Button>
      ),
    },
  ];

  return (
    <div className="qy-page">
      <PageHeader
        title="治理看板"
        subtitle="重复 / 过期 / 孤立 / 冲突 / 与商品主数据不一致"
        breadcrumb={[{ label: '运营后台', to: ROUTES.adminDashboard }, { label: '治理看板' }]}
        extra={<Button onClick={() => void query.refetch()}>重新计算</Button>}
      />

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {CATEGORIES.map((category) => (
          <Col xs={12} sm={8} lg={4} key={category.key}>
            <StatCard title={category.label} value={report.counts[category.key] ?? 0} />
          </Col>
        ))}
      </Row>

      <Card>
        <Tabs
          items={CATEGORIES.map((category) => ({
            key: category.key,
            label: `${category.label}（${report[category.key].length}）`,
            children: report[category.key].length === 0 ? (
              <EmptyState title="这一类没有问题" />
            ) : (
              <Table<GovernanceItem>
                rowKey={(row) => `${row.type}-${row.document_id ?? row.title}`}
                size="small"
                columns={columns}
                dataSource={report[category.key]}
                pagination={{ pageSize: 10 }}
              />
            ),
          }))}
        />
        <Typography.Text type="secondary">
          冲突类为阻断级规则冲突：未解决时任何版本都无法发布；解决入口在规则 API / 治理报告详情。
        </Typography.Text>
      </Card>
    </div>
  );
}
