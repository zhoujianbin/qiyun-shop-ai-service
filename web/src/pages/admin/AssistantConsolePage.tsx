import App from 'antd/es/app';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Col from 'antd/es/col';
import Input from 'antd/es/input';
import Modal from 'antd/es/modal';
import List from 'antd/es/list';
import Row from 'antd/es/row';
import Space from 'antd/es/space';
import Table from 'antd/es/table';
import Tooltip from 'antd/es/tooltip';
import Tag from 'antd/es/tag';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { errorMessage } from '@/api/errors';
import { assistantApi } from '@/api/endpoints/assistant';
import { queryClient } from '@/app/providers';
import { EmptyState } from '@/components/common/EmptyState';
import { ErrorState } from '@/components/common/ErrorState';
import { PageHeader } from '@/components/common/PageHeader';
import { usePermission } from '@/hooks/usePermission';
import { ROUTES } from '@/constants/routes';
import { P } from '@/types/permissions';
import type { ChatMessage, Conversation, Handoff } from '@/types/assistant';

/** 会话号缩略：展示开头与末尾，悬停看全量，点击复制。 */
function ConversationNo({ value }: { value?: string | null }) {
  const { message } = App.useApp();
  if (!value) return <Typography.Text type="secondary">-</Typography.Text>;
  const short = value.length > 12 ? `${value.slice(0, 8)}…${value.slice(-2)}` : value;
  return (
    <Tooltip title={<span>{value}<br /><Typography.Text type="secondary" style={{ fontSize: 12 }}>点击复制</Typography.Text></span>}>
      <Typography.Text
        code
        style={{ cursor: 'pointer' }}
        onClick={() => {
          void navigator.clipboard.writeText(value).then(
            () => message.success('已复制会话号'),
            () => message.warning('复制失败，请手动选择'),
          );
        }}
      >
        {short}
      </Typography.Text>
    </Tooltip>
  );
}

/** 客服工作台：转人工队列 + 会话回话（认领即暂停 AI，关单需结论）。 */
export default function AssistantConsolePage() {
  const { message } = App.useApp();
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [reply, setReply] = useState('');
  const [closing, setClosing] = useState<Handoff | null>(null);
  const [closeSummary, setCloseSummary] = useState('');
  const canHandle = usePermission(P.aiHandoffWrite);

  const handoffs = useQuery({
    queryKey: ['assistant', 'handoffs'],
    queryFn: () => assistantApi.handoffs(),
  });
  const conversations = useQuery({
    queryKey: ['assistant', 'conversations'],
    queryFn: () => assistantApi.conversations({ page: 1, page_size: 20 }),
  });
  const messages = useQuery({
    queryKey: ['assistant', 'messages', conversationId],
    queryFn: () => assistantApi.messages(conversationId as number, { page: 1, page_size: 50 }),
    enabled: conversationId !== null,
  });

  // 轮询当前会话：回答生成中也能看到近似实时内容
  useEffect(() => {
    if (conversationId === null) return;
    const timer = window.setInterval(() => {
      void queryClient.invalidateQueries({ queryKey: ['assistant', 'messages', conversationId] });
      void queryClient.invalidateQueries({ queryKey: ['assistant', 'handoffs'] });
    }, 1500);
    return () => window.clearInterval(timer);
  }, [conversationId]);

  const claim = useMutation({
    mutationFn: (id: number) => assistantApi.claimHandoff(id),
    onSuccess: async () => {
      message.success('已接单，AI 已暂停');
      await queryClient.invalidateQueries({ queryKey: ['assistant'] });
    },
    onError: (error) => message.error(errorMessage(error)),
  });

  const close = useMutation({
    mutationFn: (payload: { id: number; summary: string }) =>
      assistantApi.closeHandoff(payload.id, { summary: payload.summary, back_to_ai: true }),
    onSuccess: async () => {
      message.success('已关闭并恢复 AI');
      setCloseSummary('');
      setClosing(null);
      await queryClient.invalidateQueries({ queryKey: ['assistant'] });
    },
    onError: (error) => message.error(errorMessage(error)),
  });

  const sendReply = useMutation({
    mutationFn: () => assistantApi.agentMessage(conversationId as number, { content: reply }),
    onSuccess: async () => {
      setReply('');
      await queryClient.invalidateQueries({ queryKey: ['assistant'] });
    },
    onError: (error) => message.error(errorMessage(error)),
  });

  const sendingClose = (row: Handoff) => close.isPending && closing?.id === row.id;

  const columns: ColumnsType<Handoff> = [
    { title: '#', dataIndex: 'id', width: 56 },
    {
      title: '会话内容',
      dataIndex: 'title',
      ellipsis: true,
      render: (value: string | null, row) => value || `会话 #${row.conversation_id}`,
    },
    {
      title: '会话号',
      dataIndex: 'conversation_no',
      width: 140,
      render: (value: string | null) => <ConversationNo value={value} />,
    },
    { title: '原因', dataIndex: 'reason', width: 160, render: (value: string) => <Tag>{value}</Tag> },
    { title: '状态', dataIndex: 'status', width: 100, render: (value: string) => <Tag color={value === 'OPEN' ? 'red' : 'blue'}>{value}</Tag> },
    {
      title: '操作',
      width: 260,
      render: (_value, row) => (
        <Space>
          <Button size="small" onClick={() => setConversationId(row.conversation_id)}>查看</Button>
          {canHandle && row.status !== 'CLOSED' ? (
            <>
              <Button size="small" type="primary" onClick={() => claim.mutate(row.id)}>接单</Button>
              <Button size="small" disabled={sendingClose(row)} onClick={() => setClosing(row)}>关单</Button>
            </>
          ) : null}
        </Space>
      ),
    },
  ];

  const conversationColumns: ColumnsType<Conversation> = [
    {
      title: '会话内容',
      dataIndex: 'title',
      ellipsis: true,
      render: (value: string | null, row) => value || `会话 #${row.id}`,
    },
    {
      title: '会话号',
      dataIndex: 'conversation_no',
      width: 140,
      render: (value: string) => <ConversationNo value={value} />,
    },
    { title: '消息', dataIndex: 'message_count', width: 70 },
    { title: '状态', dataIndex: 'status', width: 100, render: (value: string) => <Tag>{value}</Tag> },
    {
      title: 'AI',
      dataIndex: 'ai_paused',
      width: 90,
      render: (value: boolean) => (value ? <Tag color="orange">已暂停</Tag> : <Tag>自动</Tag>),
    },
    { title: '', render: (_v, row) => <Button size="small" onClick={() => setConversationId(row.id)}>打开</Button> },
  ];

  return (
    <div className="qy-page">
      <PageHeader
        title="客服工作台"
        subtitle="转人工队列与会话回话；接单后 AI 停止自动回答"
        breadcrumb={[{ label: '运营后台', to: ROUTES.adminDashboard }, { label: '客服工作台' }]}
      />

      <Row gutter={16}>
        <Col xs={24} lg={12}>
          <Card title="转人工队列" size="small" style={{ marginBottom: 16 }}>
            {handoffs.error ? <ErrorState error={handoffs.error} onRetry={() => void handoffs.refetch()} /> : (
              <Table<Handoff>
                rowKey="id" size="small" columns={columns}
                dataSource={handoffs.data ?? []} pagination={false}
                locale={{ emptyText: <EmptyState title="没有待处理转人工" /> }}
              />
            )}
          </Card>

          <Card title="会话列表" size="small">
            <Table<Conversation>
              rowKey="id" size="small" columns={conversationColumns}
              dataSource={conversations.data?.items ?? []} pagination={false}
            />
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title={conversationId ? `会话 #${conversationId}` : '选择一条会话'} size="small">
            {conversationId === null ? <EmptyState title="从左侧选择会话" /> : messages.error ? (
              <ErrorState error={messages.error} onRetry={() => void messages.refetch()} />
            ) : (
              <>
                <List
                  size="small"
                  style={{ maxHeight: 360, overflowY: 'auto' }}
                  dataSource={messages.data?.items ?? []}
                  renderItem={(item: ChatMessage) => (
                    <List.Item>
                      <Space direction="vertical" size={2} style={{ width: '100%' }}>
                        <Space size={6}>
                          <Tag color={item.role === 'USER' ? 'blue' : item.role === 'AGENT' ? 'orange' : 'default'}>
                            {item.role}
                          </Tag>
                          {item.status === 'STREAMING' ? <Tag color="processing">生成中</Tag> : null}
                          {item.status === 'FAILED' ? <Tag color="red">失败</Tag> : null}
                          {item.status === 'REFUSED' ? <Tag>拒答</Tag> : null}
                        </Space>
                        <Typography.Text>
                          {item.content || (item.status === 'STREAMING' ? '正在生成…' : '')}
                          {item.status === 'STREAMING' && item.content ? ' ▌' : ''}
                        </Typography.Text>
                      </Space>
                    </List.Item>
                  )}
                />
                {canHandle ? (
                  <Space.Compact style={{ width: '100%', marginTop: 12 }}>
                    <Input
                      placeholder="以人工身份回复"
                      value={reply}
                      onChange={(event) => setReply(event.target.value)}
                    />
                    <Button type="primary" disabled={!reply.trim()} onClick={() => sendReply.mutate()}>发送</Button>
                  </Space.Compact>
                ) : null}
              </>
            )}
          </Card>
        </Col>
      </Row>

      <Modal
        open={closing !== null}
        title={`关闭转人工 #${closing?.id ?? ''}`}
        okText="确认关单"
        cancelText="取消"
        confirmLoading={close.isPending}
        okButtonProps={{ disabled: !closeSummary.trim() }}
        onOk={() => {
          if (!closing) return;
          if (!closeSummary.trim()) {
            message.warning('关单必须填写结论');
            return;
          }
          close.mutate({ id: closing.id, summary: closeSummary.trim() });
        }}
        onCancel={() => {
          setClosing(null);
          setCloseSummary('');
        }}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Typography.Text type="secondary">填写处理结论（必填），关闭后 AI 会恢复自动回答。</Typography.Text>
          <Input.TextArea
            rows={3}
            maxLength={2000}
            showCount
            placeholder="例如：已电话联系客户，指导更换电池后恢复"
            value={closeSummary}
            onChange={(event) => setCloseSummary(event.target.value)}
          />
        </Space>
      </Modal>
    </div>
  );
}
