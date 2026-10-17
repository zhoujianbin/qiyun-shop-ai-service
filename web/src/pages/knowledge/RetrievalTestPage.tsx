import Alert from 'antd/es/alert';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Descriptions from 'antd/es/descriptions';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import InputNumber from 'antd/es/input-number';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Table from 'antd/es/table';
import Tag from 'antd/es/tag';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { errorMessage } from '@/api/errors';
import { knowledgeApi } from '@/api/endpoints/knowledge';
import { ErrorState } from '@/components/common/ErrorState';
import { PageHeader } from '@/components/common/PageHeader';
import { ROUTES } from '@/constants/routes';
import type { RetrievalHit, RetrievalResult } from '@/types/knowledge';

interface RetrievalForm {
  query: string;
  top_k: number;
  category?: string;
  identity_level: string;
}

/** 检索测试：命中片段 + 引用路径 + 三路分数与耗时。 */
export default function RetrievalTestPage() {
  const [form] = Form.useForm<RetrievalForm>();
  const [result, setResult] = useState<RetrievalResult | null>(null);

  const mutation = useMutation({
    mutationFn: (values: RetrievalForm) => knowledgeApi.retrievalTest({
      query: values.query,
      top_k: values.top_k,
      filters: values.category ? { category: values.category } : {},
      identity_level: values.identity_level,
    }),
    onSuccess: (data) => setResult(data),
    onError: (error) => setResult(null),
  });

  const columns: ColumnsType<RetrievalHit> = [
    { title: '文档', dataIndex: 'document_id', width: 220 },
    { title: '版本', dataIndex: 'version', width: 70 },
    { title: '标题路径', dataIndex: 'title_path', width: 260, render: (value: string) => value || '—' },
    {
      title: '原文行',
      width: 110,
      render: (_value, row) => (row.line_start ? `L${row.line_start}-${row.line_end ?? row.line_start}` : '—'),
    },
    { title: '融合分', width: 100, render: (_value, row) => result?.debug.fused_score[String(row.chunk_id)] ?? '—' },
    { title: '片段', dataIndex: 'snippet', ellipsis: true },
  ];

  return (
    <div className="qy-page">
      <PageHeader
        title="检索测试"
        subtitle="混合检索（全文 + 向量，RRF 融合）；命中可回指原文行号"
        breadcrumb={[{ label: '运营后台', to: ROUTES.adminDashboard }, { label: '检索测试' }]}
      />

      <Card style={{ marginBottom: 16 }}>
        <Form
          form={form}
          layout="inline"
          initialValues={{ top_k: 10, identity_level: 'public' }}
          onFinish={(values) => mutation.mutate(values)}
        >
          <Form.Item name="query" rules={[{ required: true, message: '请输入查询' }]} style={{ minWidth: 320 }}>
            <Input placeholder="例如：门锁电池续航多久" allowClear />
          </Form.Item>
          <Form.Item name="top_k" label="TopK">
            <InputNumber min={1} max={50} />
          </Form.Item>
          <Form.Item name="category" label="类目">
            <Input placeholder="可选" style={{ width: 160 }} allowClear />
          </Form.Item>
          <Form.Item name="identity_level" label="身份等级">
            <Select
              style={{ width: 140 }}
              options={[
                { value: 'public', label: '公开' },
                { value: 'customer', label: '客户' },
                { value: 'agent', label: '客服' },
              ]}
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={mutation.isPending}>检索</Button>
          </Form.Item>
        </Form>
      </Card>

      {mutation.error ? <ErrorState error={mutation.error} /> : null}

      {result ? (
        <>
          <Card style={{ marginBottom: 16 }} title="本次检索">
            <Descriptions size="small" column={{ xs: 1, sm: 2, lg: 4 }}>
              <Descriptions.Item label="命中">{result.hits.length}</Descriptions.Item>
              <Descriptions.Item label="耗时">{result.debug.latency_ms} ms</Descriptions.Item>
              <Descriptions.Item label="候选">{result.debug.candidates ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="说明">
                <Tag>分数只在调试段，不作为引用</Tag>
              </Descriptions.Item>
            </Descriptions>
          </Card>

          {result.hits.length === 0 ? (
            <Alert type="warning" showIcon message="没有命中" description="可能是查询与语料无关、过滤条件过严，或相关版本尚未发布/向量未就绪。" />
          ) : (
            <Card title="命中列表">
              <Table<RetrievalHit>
                rowKey="chunk_id"
                size="small"
                columns={columns}
                dataSource={result.hits}
                pagination={false}
                expandable={{
                  expandedRowRender: (row) => (
                    <Space direction="vertical" size={2}>
                      <Typography.Text>向量分：{result.debug.vector_score[String(row.chunk_id)] ?? '—'}</Typography.Text>
                      <Typography.Text>全文分：{result.debug.text_score[String(row.chunk_id)] ?? '—'}</Typography.Text>
                      <Typography.Text>融合分：{result.debug.fused_score[String(row.chunk_id)] ?? '—'}</Typography.Text>
                      <Typography.Text type="secondary">{row.snippet}</Typography.Text>
                    </Space>
                  ),
                }}
              />
            </Card>
          )}
        </>
      ) : null}
    </div>
  );
}
