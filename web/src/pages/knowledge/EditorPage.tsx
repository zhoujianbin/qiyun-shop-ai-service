import Alert from 'antd/es/alert';
import App from 'antd/es/app';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Col from 'antd/es/col';
import Input from 'antd/es/input';
import List from 'antd/es/list';
import Row from 'antd/es/row';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Tag from 'antd/es/tag';
import Typography from 'antd/es/typography';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import { errorMessage } from '@/api/errors';
import { knowledgeApi } from '@/api/endpoints/knowledge';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { PageHeader } from '@/components/common/PageHeader';
import { usePermission } from '@/hooks/usePermission';
import { ROUTES } from '@/constants/routes';
import { P } from '@/types/permissions';
import type { ChunkPreviewItem } from '@/types/knowledge';

const SAMPLE = `# 产品知识

## 智能门锁

门锁使用 8 节 5 号电池，正常使用约 12 个月。

### 低电量提醒

电量低于 20% 时 App 推送提醒，仍可使用约 2 周。
`;

/** 编辑器：选择文档 → 载入当前版本 → 编辑 → 保存为新版本；切片在服务端生成（500ms 防抖预览）。 */
export default function EditorPage() {
  const { message } = App.useApp();
  const [content, setContent] = useState(SAMPLE);
  const [chunks, setChunks] = useState<ChunkPreviewItem[]>([]);
  const [documentPk, setDocumentPk] = useState<number | undefined>();
  const [changeSummary, setChangeSummary] = useState('');
  const timer = useRef<number | null>(null);
  const canWrite = usePermission(P.knowledgeDocumentWrite);

  const documents = useQuery({
    queryKey: queryKeys.knowledge.documents({ page: 1, page_size: 50 }),
    queryFn: () => knowledgeApi.documents({ page: 1, page_size: 50 }),
  });

  const detail = useQuery({
    queryKey: queryKeys.knowledge.document(documentPk ?? 0),
    queryFn: () => knowledgeApi.document(documentPk as number),
    enabled: Boolean(documentPk),
  });

  // 选中文档后载入当前版本内容
  useEffect(() => {
    const active = detail.data?.active_version;
    const latest = detail.data?.versions?.[0];
    const source = active ?? latest;
    if (source?.content_md) setContent(source.content_md);
  }, [detail.data]);

  const preview = useMutation({
    mutationFn: (value: string) => knowledgeApi.previewChunks(value),
    onSuccess: (data) => setChunks(data),
  });

  const save = useMutation({
    mutationFn: () => knowledgeApi.createVersion(documentPk as number, {
      content_md: content,
      change_summary: changeSummary || undefined,
    }),
    onSuccess: async (version) => {
      message.success(`已保存为 v${version.version}（草稿），提交审核后才可发布`);
      setChangeSummary('');
      await queryClient.invalidateQueries({ queryKey: ['knowledge'] });
    },
    onError: (error) => message.error(errorMessage(error)),
  });

  useEffect(() => {
    if (timer.current) window.clearTimeout(timer.current);
    if (!content.trim()) {
      setChunks([]);
      return;
    }
    timer.current = window.setTimeout(() => preview.mutate(content), 500);
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [content]);

  const options = useMemo(
    () => (documents.data?.items ?? []).map((item) => ({
      value: item.id,
      label: `${item.title}（${item.document_id}）`,
    })),
    [documents.data],
  );

  const loadedVersion = detail.data?.active_version ?? detail.data?.versions?.[0];

  return (
    <div className="qy-page">
      <PageHeader
        title="文档编辑"
        subtitle="选择文档 → 载入当前版本 → 编辑 → 保存为新版本；切片在服务端生成"
        breadcrumb={[{ label: '运营后台', to: ROUTES.adminDashboard }, { label: '文档编辑' }]}
        extra={
          canWrite ? (
            <Space>
              <Input
                placeholder="变更摘要（可选）"
                value={changeSummary}
                onChange={(event) => setChangeSummary(event.target.value)}
                style={{ width: 220 }}
                maxLength={200}
              />
              <Button
                type="primary"
                disabled={!documentPk || !content.trim()}
                loading={save.isPending}
                onClick={() => save.mutate()}
              >
                保存为新版本
              </Button>
            </Space>
          ) : null
        }
      />

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <span>目标文档：</span>
          <Select
            showSearch
            allowClear
            style={{ minWidth: 360 }}
            placeholder="搜索并选择要编辑的文档"
            value={documentPk}
            loading={documents.isLoading}
            options={options}
            filterOption={(input, option) => String(option?.label ?? '').includes(input)}
            onChange={(value) => setDocumentPk(value)}
          />
          {loadedVersion ? (
            <Typography.Text type="secondary">
              当前版本 v{loadedVersion.version} · {loadedVersion.status}
            </Typography.Text>
          ) : null}
        </Space>
        {!documentPk ? (
          <Alert
            style={{ marginTop: 12 }}
            type="info"
            showIcon
            message="先选择一份文档"
            description="选中后会自动载入其当前生效版本的内容；保存会新建一个草稿版本，不会改动已有版本。"
          />
        ) : null}
      </Card>

      <Row gutter={16}>
        <Col xs={24} lg={12}>
          <Card title="Markdown 源文" size="small">
            <Input.TextArea
              rows={20}
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder="在此粘贴或编写 Markdown"
            />
            <Typography.Text type="secondary">停止输入 500ms 后自动刷新右侧预览</Typography.Text>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="渲染预览" size="small" style={{ marginBottom: 16 }}>
            <div className="qy-markdown-preview" style={{ maxHeight: 240, overflow: 'auto' }}>
              <ReactMarkdown>{content}</ReactMarkdown>
            </div>
          </Card>
          <Card title={`切片预览（${chunks.length} 片）`} size="small" loading={preview.isPending}>
            {chunks.length === 0 ? (
              <Typography.Text type="secondary">还没有切片；输入内容后自动生成</Typography.Text>
            ) : (
              <List
                size="small"
                dataSource={chunks}
                renderItem={(item) => (
                  <List.Item>
                    <Space direction="vertical" size={2} style={{ width: '100%' }}>
                      <Space wrap>
                        <Tag>#{item.ord}</Tag>
                        <Tag color={item.char_count > 600 ? 'red' : item.char_count < 200 ? 'orange' : 'green'}>
                          {item.char_count} 字
                        </Tag>
                        <Typography.Text type="secondary">
                          L{item.line_start}-{item.line_end} · {item.title_path || '（无标题）'}
                        </Typography.Text>
                      </Space>
                      <Typography.Text style={{ fontSize: 12 }} ellipsis>
                        {item.content.replace(/\n/g, ' ')}
                      </Typography.Text>
                    </Space>
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
