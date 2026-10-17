import App from 'antd/es/app';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Table from 'antd/es/table';
import type { ColumnsType } from 'antd/es/table';
import Upload from 'antd/es/upload';
import type { UploadFile } from 'antd/es/upload/interface';
import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { errorMessage } from '@/api/errors';
import { knowledgeApi } from '@/api/endpoints/knowledge';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { EmptyState } from '@/components/common/EmptyState';
import { ErrorState } from '@/components/common/ErrorState';
import { PageHeader } from '@/components/common/PageHeader';
import { StatusTag } from '@/components/common/StatusTag';
import { usePermission } from '@/hooks/usePermission';
import { ROUTES } from '@/constants/routes';
import { P } from '@/types/permissions';
import type { KnowledgeDocument } from '@/types/knowledge';

const STATUS_OPTIONS = [
  { value: 'DRAFT', label: '草稿' },
  { value: 'REVIEWING', label: '审核中' },
  { value: 'ACTIVE', label: '生效' },
  { value: 'ARCHIVED', label: '归档' },
];

/** 知识文档列表：筛选走 URL query，便于治理报告下钻。 */
export default function DocumentListPage() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [keyword, setKeyword] = useState(params.get('keyword') ?? '');
  const [files, setFiles] = useState<UploadFile[]>([]);
  const canImport = usePermission(P.knowledgeDocumentImport);

  const queryParams = useMemo(() => ({
    keyword: params.get('keyword') ?? undefined,
    category: params.get('category') ?? undefined,
    status: params.get('status') ?? undefined,
    page: Number(params.get('page') ?? 1),
    page_size: 20,
  }), [params]);

  const query = useQuery({
    queryKey: queryKeys.knowledge.documents(queryParams),
    queryFn: () => knowledgeApi.documents(queryParams),
  });

  const importMutation = useMutation({
    mutationFn: () => knowledgeApi.importFiles(files.map((file) => file.originFileObj as File)),
    onSuccess: async (job) => {
      message.success(`导入完成：成功 ${job.succeeded}，跳过 ${job.skipped}，失败 ${job.failed}`);
      setFiles([]);
      await queryClient.invalidateQueries({ queryKey: ['knowledge'] });
    },
    onError: (error) => message.error(errorMessage(error)),
  });

  const applyFilter = (patch: Record<string, string | undefined>) => {
    const next = new URLSearchParams(params);
    Object.entries(patch).forEach(([key, value]) => {
      if (value) next.set(key, value);
      else next.delete(key);
    });
    next.delete('page');
    setParams(next);
  };

  const columns: ColumnsType<KnowledgeDocument> = [
    {
      title: '文档',
      dataIndex: 'title',
      render: (_value, row) => (
        <Space direction="vertical" size={0}>
          <Button type="link" style={{ padding: 0 }} onClick={() => navigate(ROUTES.knowledgeDocument(row.id))}>
            {row.title}
          </Button>
          <span style={{ color: 'var(--color-text-secondary)', fontSize: 12 }}>{row.document_id}</span>
        </Space>
      ),
    },
    { title: '类目', dataIndex: 'category', width: 160 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (value: string) => <StatusTag kind="product" value={value === 'ACTIVE' ? 'ON_SALE' : 'OFF_SHELF'} />,
    },
    { title: '当前版本', dataIndex: 'current_version', width: 100, render: (value?: number | null) => value ?? '—' },
    { title: '责任', dataIndex: 'owner', width: 140, render: (value?: string | null) => value || '—' },
  ];

  return (
    <div className="qy-page">
      <PageHeader
        title="知识文档"
        subtitle="导入、筛选、进入详情发布或回滚"
        breadcrumb={[{ label: '运营后台', to: ROUTES.adminDashboard }, { label: '知识文档' }]}
        extra={
          canImport ? (
            <Space>
              <Upload
                multiple
                beforeUpload={() => false}
                fileList={files}
                onChange={({ fileList }) => setFiles(fileList)}
                accept=".md,.txt,.docx,.yaml"
              >
                <Button>选择文件</Button>
              </Upload>
              <Button
                type="primary"
                disabled={files.length === 0}
                loading={importMutation.isPending}
                onClick={() => importMutation.mutate()}
              >
                开始导入（{files.length}）
              </Button>
            </Space>
          ) : null
        }
      />

      <Card>
        <Space wrap style={{ marginBottom: 16 }}>
          <Input.Search
            placeholder="按标题或 document_id 搜索"
            value={keyword}
            allowClear
            style={{ width: 260 }}
            onChange={(event) => setKeyword(event.target.value)}
            onSearch={(value) => applyFilter({ keyword: value || undefined })}
          />
          <Select
            placeholder="类目"
            allowClear
            style={{ width: 180 }}
            value={params.get('category') ?? undefined}
            onChange={(value) => applyFilter({ category: value })}
            options={[...new Set((query.data?.items ?? []).map((item) => item.category))]
              .map((value) => ({ value, label: value }))}
          />
          <Select
            placeholder="状态"
            allowClear
            style={{ width: 140 }}
            value={params.get('status') ?? undefined}
            onChange={(value) => applyFilter({ status: value })}
            options={STATUS_OPTIONS}
          />
        </Space>

        {query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : (
          <Table<KnowledgeDocument>
            rowKey="id"
            loading={query.isLoading}
            columns={columns}
            dataSource={query.data?.items ?? []}
            locale={{ emptyText: <EmptyState title="还没有知识文档" description="从右上角导入 Markdown 开始" /> }}
            pagination={{
              current: queryParams.page,
              pageSize: 20,
              total: query.data?.total ?? 0,
              onChange: (page) => applyFilter({ page: String(page) }),
            }}
          />
        )}
      </Card>
    </div>
  );
}
