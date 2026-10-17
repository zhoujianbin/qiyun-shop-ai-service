import App from 'antd/es/app';
import Alert from 'antd/es/alert';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Drawer from 'antd/es/drawer';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import List from 'antd/es/list';
import Modal from 'antd/es/modal';
import Radio from 'antd/es/radio';
import Space from 'antd/es/space';
import Table from 'antd/es/table';
import Tag from 'antd/es/tag';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { errorMessage } from '@/api/errors';
import { knowledgeApi } from '@/api/endpoints/knowledge';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { EmptyState } from '@/components/common/EmptyState';
import { ErrorState } from '@/components/common/ErrorState';
import { PageHeader } from '@/components/common/PageHeader';
import { ROUTES } from '@/constants/routes';
import type { ReviewTask } from '@/types/knowledge';

const DECISIONS = [
  { value: 'APPROVED', label: '通过' },
  { value: 'CHANGES_REQUESTED', label: '退回修改' },
  { value: 'REJECTED', label: '拒绝' },
];

/** 审核队列：认领、批注锚定、通过/退回/拒绝、冲突提示。 */
export default function ReviewPage() {
  const { message } = App.useApp();
  const [decideTask, setDecideTask] = useState<ReviewTask | null>(null);
  const [commentTask, setCommentTask] = useState<ReviewTask | null>(null);
  const [form] = Form.useForm<{ decision: string; note: string }>();
  const [commentForm] = Form.useForm<{ title_path: string; content: string }>();

  const tasks = useQuery({
    queryKey: queryKeys.knowledge.reviewTasks({ status: 'PENDING' }),
    queryFn: () => knowledgeApi.reviewTasks({ status: 'PENDING' }),
  });

  const comments = useQuery({
    queryKey: queryKeys.knowledge.comments(commentTask?.id ?? 0),
    queryFn: () => knowledgeApi.comments(commentTask!.id),
    enabled: Boolean(commentTask),
  });

  const claim = useMutation({
    mutationFn: (taskId: number) => knowledgeApi.claimTask(taskId),
    onSuccess: async () => {
      message.success('已认领');
      await queryClient.invalidateQueries({ queryKey: ['knowledge'] });
    },
    onError: (error) => message.error(errorMessage(error)),
  });

  const decide = useMutation({
    mutationFn: (values: { decision: string; note: string }) =>
      knowledgeApi.decideTask(decideTask!.id, values),
    onSuccess: async (task) => {
      message.success(`已${task.decision === 'APPROVED' ? '通过' : '处理'}${task.self_review ? '（自审）' : ''}`);
      setDecideTask(null);
      form.resetFields();
      await queryClient.invalidateQueries({ queryKey: ['knowledge'] });
    },
    onError: (error) => message.error(errorMessage(error)),
  });

  const addComment = useMutation({
    mutationFn: (values: { title_path: string; content: string }) =>
      knowledgeApi.addComment(commentTask!.id, {
        anchor: { title_path: values.title_path, chunk_ord: 0 },
        content: values.content,
      }),
    onSuccess: async () => {
      message.success('批注已保存');
      commentForm.resetFields();
      await queryClient.invalidateQueries({ queryKey: ['knowledge'] });
    },
    onError: (error) => message.error(errorMessage(error)),
  });

  const columns: ColumnsType<ReviewTask> = [
    {
      title: '文档',
      render: (_value, row) => (
        <Space direction="vertical" size={0}>
          <Typography.Text strong>{row.document?.title ?? `版本 #${row.document_version_id}`}</Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {row.document?.document_id} · v{row.version?.version}
          </Typography.Text>
        </Space>
      ),
    },
    { title: '状态', dataIndex: 'status', width: 110, render: (value: string) => <Tag>{value}</Tag> },
    {
      title: '自审',
      dataIndex: 'self_review',
      width: 90,
      render: (value: boolean) => (value ? <Tag color="orange">自审</Tag> : '—'),
    },
    {
      title: '操作',
      width: 260,
      render: (_value, row) => (
        <Space>
          <Button size="small" onClick={() => claim.mutate(row.id)}>认领</Button>
          <Button size="small" type="primary" onClick={() => { setDecideTask(row); form.setFieldsValue({ decision: 'APPROVED' }); }}>
            审核
          </Button>
          <Button size="small" onClick={() => setCommentTask(row)}>批注</Button>
        </Space>
      ),
    },
  ];

  return (
    <div className="qy-page">
      <PageHeader
        title="审核队列"
        subtitle="认领后给出通过 / 退回 / 拒绝，理由必填"
        breadcrumb={[{ label: '运营后台', to: ROUTES.adminDashboard }, { label: '审核队列' }]}
      />

      <Card>
        {tasks.error ? <ErrorState error={tasks.error} onRetry={() => void tasks.refetch()} /> : (
          <Table<ReviewTask>
            rowKey="id"
            loading={tasks.isLoading}
            columns={columns}
            dataSource={tasks.data ?? []}
            locale={{ emptyText: <EmptyState title="没有待审任务" description="提交版本审核后会出现在这里" /> }}
            pagination={false}
          />
        )}
      </Card>

      <Modal
        open={Boolean(decideTask)}
        title={`审核：${decideTask?.document?.title ?? ''}`}
        okText="提交决定"
        cancelText="取消"
        confirmLoading={decide.isPending}
        onCancel={() => setDecideTask(null)}
        onOk={() => form.submit()}
        destroyOnClose
      >
        {decideTask?.self_review ? (
          <Alert type="warning" showIcon style={{ marginBottom: 12 }} message="自审版本" description="该版本由你提交，决定会标注 self_review。" />
        ) : null}
        <Form form={form} layout="vertical" onFinish={(values) => decide.mutate(values)}>
          <Form.Item name="decision" label="决定" rules={[{ required: true }]}>
            <Radio.Group options={DECISIONS} />
          </Form.Item>
          <Form.Item name="note" label="理由" rules={[{ required: true, message: '决定必须填写理由' }]}>
            <Input.TextArea rows={3} maxLength={2000} showCount />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        open={Boolean(commentTask)}
        title="批注"
        width={480}
        onClose={() => setCommentTask(null)}
      >
        <Form form={commentForm} layout="vertical" onFinish={(values) => addComment.mutate(values)}>
          <Form.Item name="title_path" label="锚定标题路径" rules={[{ required: true, message: '必须锚定到标题路径或切片' }]}>
            <Input placeholder="例如：产品知识 / 智能门锁 / 电池续航" />
          </Form.Item>
          <Form.Item name="content" label="批注内容" rules={[{ required: true, message: '批注不能为空' }]}>
            <Input.TextArea rows={3} maxLength={4000} showCount />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={addComment.isPending}>保存批注</Button>
        </Form>

        <List
          style={{ marginTop: 16 }}
          size="small"
          dataSource={comments.data ?? []}
          locale={{ emptyText: '还没有批注' }}
          renderItem={(item) => (
            <List.Item>
              <Space direction="vertical" size={2}>
                <Typography.Text strong>{String(item.anchor.title_path ?? '（无锚点）')}</Typography.Text>
                <Typography.Text>{item.content}</Typography.Text>
              </Space>
            </List.Item>
          )}
        />
      </Drawer>
    </div>
  );
}
