import Alert from 'antd/es/alert';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Col from 'antd/es/col';
import Row from 'antd/es/row';
import Space from 'antd/es/space';
import Typography from 'antd/es/typography';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { knowledgeApi } from '@/api/endpoints/knowledge';
import { queryKeys } from '@/api/queryKeys';
import { ErrorState } from '@/components/common/ErrorState';
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton';
import { PageHeader } from '@/components/common/PageHeader';
import { StatCard } from '@/components/common/StatCard';
import { ROUTES } from '@/constants/routes';

/** 知识库概览：四张卡 + 治理计数 + 快捷入口。 */
export default function OverviewPage() {
  const query = useQuery({
    queryKey: queryKeys.knowledge.overview(),
    queryFn: () => knowledgeApi.overview(),
  });

  if (query.isLoading) return <LoadingSkeleton rows={6} />;
  if (query.error) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;

  const data = query.data!;
  const governance = data.governance ?? {};

  return (
    <div className="qy-page">
      <PageHeader
        title="知识概览"
        subtitle="知识资产规模、待审与治理风险的一页视图"
        breadcrumb={[{ label: '运营后台', to: ROUTES.adminDashboard }, { label: '知识概览' }]}
        extra={
          <Space wrap>
            <Link to={ROUTES.knowledgeDocuments}><Button type="primary">文档管理</Button></Link>
            <Link to={ROUTES.knowledgeRetrieval}><Button>检索测试</Button></Link>
            <Link to={ROUTES.knowledgeGovernance}><Button>治理看板</Button></Link>
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}><StatCard title="知识文档" value={data.documents} hint="含草稿与已归档" /></Col>
        <Col xs={24} sm={12} lg={6}><StatCard title="切片总数" value={data.chunks} hint="已切分并等待/完成向量化" /></Col>
        <Col xs={24} sm={12} lg={6}><StatCard title="待审任务" value={data.pending_review} hint="PENDING + CLAIMED" /></Col>
        <Col xs={24} sm={12} lg={6}><StatCard title="未解决冲突" value={data.conflicts} hint="阻断级规则冲突" /></Col>
      </Row>

      <Card style={{ marginTop: 16 }} title="治理计数">
        <Space size={24} wrap>
          {[
            ['重复', 'duplicate'],
            ['过期', 'expired'],
            ['孤立', 'orphan'],
            ['冲突', 'conflict'],
            ['与商品不一致', 'inconsistent'],
          ].map(([label, key]) => (
            <Typography.Text key={key}>
              {label}：<Typography.Text strong>{governance[key] ?? 0}</Typography.Text>
            </Typography.Text>
          ))}
        </Space>
      </Card>

      {data.conflicts > 0 ? (
        <Alert
          style={{ marginTop: 16 }}
          type="warning"
          showIcon
          message="存在未解决的阻断级规则冲突"
          description="阻断级冲突未解决时，任何版本都无法发布。请到治理看板查看并标记解决。"
          action={<Link to={ROUTES.knowledgeGovernance}><Button size="small">去处理</Button></Link>}
        />
      ) : null}
    </div>
  );
}
