import App from 'antd/es/app';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Descriptions from 'antd/es/descriptions';
import Space from 'antd/es/space';
import Table from 'antd/es/table';
import Tag from 'antd/es/tag';
import Timeline from 'antd/es/timeline';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { errorMessage } from '@/api/errors';
import { knowledgeApi } from '@/api/endpoints/knowledge';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { EmptyState } from '@/components/common/EmptyState';
import { ErrorState } from '@/components/common/ErrorState';
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton';
import { PageHeader } from '@/components/common/PageHeader';
import { PublishModal } from '@/components/knowledge/PublishModal';
import { usePermission } from '@/hooks/usePermission';
import { ROUTES } from '@/constants/routes';
import { P } from '@/types/permissions';
import type { KnowledgeChunk, KnowledgeVersion } from '@/types/knowledge';

const PAGE_SIZE = 10;

/** 文档详情：元数据 + 版本时间线 + 生效版本切片 + 发布/回滚入口。 */
export default function DocumentDetailPage() {
  const { message } = App.useApp();
  const { documentPk } = useParams<{ documentPk: string }>();
  const [page, setPage] = useState(1);
  const [publishOpen, setPublishOpen] = useState(false);
  const [publishVersion, setPublishVersion] = useState<number | null>(null);
  const canPublish = usePermission(P.knowledgeDocumentPublish);
  const canRollback = usePermission(P.knowledgeDocumentRollback);
  const canWrite = usePermission(P.knowledgeDocumentWrite);

  const detail = useQuery({
    queryKey: queryKeys.knowledge.document(documentPk ?? ''),
    queryFn: () => knowledgeApi.document(documentPk as string),
    enabled: Boolean(documentPk),
  });

  const activeVersionId = detail.data?.active_version?.id;
  const chunks = useQuery({
    queryKey: queryKeys.knowledge.chunks(activeVersionId ?? 0, { page, page_size: PAGE_SIZE }),
    queryFn: () => knowledgeApi.chunks(activeVersionId as number, { page, page_size: PAGE_SIZE }),
    enabled: Boolean(activeVersionId),
  });

  const submitMutation = useMutation({
    mutationFn: (versionId: number) => knowledgeApi.submit(versionId),
    onSuccess: async () => {
      message.success('已提交审核');
      await queryClient.invalidateQueries({ queryKey: ['knowledge'] });
    },
    onError: (error) => message.error(errorMessage(error)),
  });

  const rollbackMutation = useMutation({
    mutationFn: (versionId: number) => knowledgeApi.rollback(versionId),
    onSuccess: async () => {
      message.success('已回滚并生成新版本');
      await queryClient.invalidateQueries({ queryKey: ['knowledge'] });
    },
    onError: (error) => message.error(errorMessage(error)),
  });

  if (detail.isLoading) return <LoadingSkeleton rows={8} />;
  if (detail.error) return <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />;

  const document = detail.data!;
  const versions = document.versions ?? [];
  const latest = versions[0];

  const chunkColumns: ColumnsType<KnowledgeChunk> = [
    { title: '#', dataIndex: 'ord', width: 60 },
    { title: '标题路径', dataIndex: 'title_path', width: 240, render: (value: string) => value || '—' },
    { title: '原文行', width: 110, render: (_v, row) => (row.line_start ? `L${row.line_start}-${row.line_end ?? row.line_start}` : '—') },
    { title: '字数', dataIndex: 'char_count', width: 80 },
    { title: '向量', dataIndex: 'embedding_status', width: 100, render: (value: string) => <Tag>{value}</Tag> },
    { title: '内容', dataIndex: 'content', ellipsis: true },
  ];

  return (
    <div className="qy-page">
      <PageHeader
        title={document.title}
        subtitle={document.document_id}
        breadcrumb={[
          { label: '运营后台', to: ROUTES.adminDashboard },
          { label: '知识文档', to: ROUTES.knowledgeDocuments },
          { label: document.title },
        ]}
        tags={<Tag>{document.status}</Tag>}
        extra={
          <Space>
            {canWrite && latest && latest.status === 'DRAFT' ? (
              <Button onClick={() => submitMutation.mutate(latest.id)} loading={submitMutation.isPending}>
                提交审核
              </Button>
            ) : null}
            {canPublish && latest ? (
              <Button type="primary" onClick={() => { setPublishVersion(latest.id); setPublishOpen(true); }}>
                发布
              </Button>
            ) : null}
          </Space>
        }
      />

      <Card title="元数据" style={{ marginBottom: 16 }}>
        <Descriptions column={{ xs: 1, sm: 2, lg: 3 }} size="small">
          <Descriptions.Item label="类目">{document.category}</Descriptions.Item>
          <Descriptions.Item label="责任人">{document.owner || '—'}</Descriptions.Item>
          <Descriptions.Item label="身份等级">{document.identity_level}</Descriptions.Item>
          <Descriptions.Item label="当前版本">{document.current_version ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="切片数">{document.chunk_count ?? 0}</Descriptions.Item>
          <Descriptions.Item label="更新时间">{document.updated_at ?? '—'}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="版本时间线" style={{ marginBottom: 16 }}>
        {versions.length === 0 ? <EmptyState title="还没有版本" /> : (
          <Timeline
            items={versions.map((version: KnowledgeVersion) => ({
              color: version.status === 'ACTIVE' ? 'green' : version.status === 'SCHEDULED' ? 'blue' : 'gray',
              children: (
                <Space direction="vertical" size={2}>
                  <Space wrap>
                    <Typography.Text strong>v{version.version}</Typography.Text>
                    <Tag>{version.status}</Tag>
                    <Typography.Text type="secondary">{version.effective_from ?? '—'}</Typography.Text>
                    {canRollback ? (
                      <Button size="small" onClick={() => rollbackMutation.mutate(version.id)}>
                        回滚到此版本
                      </Button>
                    ) : null}
                  </Space>
                  <Typography.Text type="secondary">{version.change_summary || '（无变更摘要）'}</Typography.Text>
                </Space>
              ),
            }))}
          />
        )}
      </Card>

      <Card title="生效版本切片">
        {!activeVersionId ? <EmptyState title="还没有生效版本" description="发布后即可查看切片" /> : chunks.error ? (
          <ErrorState error={chunks.error} onRetry={() => void chunks.refetch()} />
        ) : (
          <Table<KnowledgeChunk>
            rowKey="id"
            size="small"
            loading={chunks.isLoading}
            columns={chunkColumns}
            dataSource={chunks.data?.items ?? []}
            pagination={{
              current: page,
              pageSize: PAGE_SIZE,
              total: chunks.data?.total ?? 0,
              onChange: setPage,
            }}
          />
        )}
      </Card>

      <PublishModal
        open={publishOpen}
        versionId={publishVersion}
        selfReview={false}
        onClose={() => setPublishOpen(false)}
      />
    </div>
  );
}
