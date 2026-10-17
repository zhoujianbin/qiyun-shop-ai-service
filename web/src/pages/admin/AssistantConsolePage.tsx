import App from 'antd/es/app';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Col from 'antd/es/col';
import Input from 'antd/es/input';
import List from 'antd/es/list';
import Row from 'antd/es/row';
import Space from 'antd/es/space';
import Table from 'antd/es/table';
import Tag from 'antd/es/tag';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
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

/** 客服工作台：转人工队列 + 会话回话（认领即暂停 AI，关单需结论）。 */
export default function AssistantConsolePage() {
  const { message } = App.useApp();
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [reply, setReply] = useState('');
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

  const claim = useMutation({
    mutationFn: (id: number) => assistantApi.claimHandoff(id),
    onSuccess: async () => {
      message.success('已接单，AI 已暂停');
      await queryClient.invalidateQueries({ queryKey: ['assistant'] });
    },
    onError: (error) => message.error(errorMessage(error)),
  });

  const close = useMutation({
    mutationFn: (id: number) => assistantApi.closeHandoff(id, { summary: closeSummary, back_to_ai: true }),
    onSuccess: async () => {
      message.success('已关闭并恢复 AI');
      setCloseSummary('');
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

  const columns: ColumnsType<Handoff> = [
    { title: '#', dataIndex: 'id', width: 60 },
    { title: '会话', dataIndex: 'conversation_id', width: 90 },
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
              <Button size="small" onClick={() => close.mutate(row.id)}>关单</Button>
            </>
          ) : null}
        </Space>
      ),
    },
  ];

  const conversationColumns: ColumnsType<Conversation> = [
    { title: '会话', dataIndex: 'conversation_no', width: 220 },
    { title: '消息', dataIndex: 'message_count', width: 80 },
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
            {canHandle ? (
              <Input
                style={{ marginTop: 12 }}
                placeholder="关单结论（关闭前填写）"
                value={closeSummary}
                onChange={(event) => setCloseSummary(event.target.value)}
              />
            ) : null}
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
                        <Tag color={item.role === 'USER' ? 'blue' : item.role === 'AGENT' ? 'orange' : 'default'}>
                          {item.role}
                        </Tag>
                        <Typography.Text>{item.content}</Typography.Text>
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
    </div>
  );
}
