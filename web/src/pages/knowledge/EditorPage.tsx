import Alert from 'antd/es/alert';
import Card from 'antd/es/card';
import Col from 'antd/es/col';
import Input from 'antd/es/input';
import List from 'antd/es/list';
import Row from 'antd/es/row';
import Space from 'antd/es/space';
import Tag from 'antd/es/tag';
import Typography from 'antd/es/typography';
import { useEffect, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import { knowledgeApi } from '@/api/endpoints/knowledge';
import { PageHeader } from '@/components/common/PageHeader';
import { ROUTES } from '@/constants/routes';
import type { ChunkPreviewItem } from '@/types/knowledge';

const SAMPLE = `# 产品知识

## 智能门锁

门锁使用 8 节 5 号电池，正常使用约 12 个月。

### 低电量提醒

电量低于 20% 时 App 推送提醒，仍可使用约 2 周。
`;

/** 编辑器：Markdown 编辑 + 只读渲染 + 服务端切片预览（500ms 防抖）。 */
export default function EditorPage() {
  const [content, setContent] = useState(SAMPLE);
  const [chunks, setChunks] = useState<ChunkPreviewItem[]>([]);
  const timer = useRef<number | null>(null);

  const preview = useMutation({
    mutationFn: (value: string) => knowledgeApi.previewChunks(value),
    onSuccess: (data) => setChunks(data),
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

  return (
    <div className="qy-page">
      <PageHeader
        title="文档编辑"
        subtitle="Markdown 编写与切片预览；切片在服务端生成，前端不自行切分"
        breadcrumb={[{ label: '运营后台', to: ROUTES.adminDashboard }, { label: '文档编辑' }]}
      />

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="本页是切片预览工作台"
        description="正式保存与提交审核走导入接口（一次请求多文件）；此处用于确认切分效果与长度是否落在 200–600 字符区间。"
      />

      <Row gutter={16}>
        <Col xs={24} lg={12}>
          <Card title="Markdown 源文" size="small">
            <Input.TextArea
              rows={22}
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder="在此粘贴或编写 Markdown"
            />
            <Typography.Text type="secondary">停止输入 500ms 后自动刷新右侧预览</Typography.Text>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="渲染预览" size="small" style={{ marginBottom: 16 }}>
            <div className="qy-markdown-preview" style={{ maxHeight: 260, overflow: 'auto' }}>
              <ReactMarkdown>{content}</ReactMarkdown>
            </div>
          </Card>
          <Card
            title={`切片预览（${chunks.length} 片）`}
            size="small"
            loading={preview.isPending}
          >
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
