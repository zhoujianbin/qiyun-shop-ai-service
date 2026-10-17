import App from 'antd/es/app';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Col from 'antd/es/col';
import Collapse from 'antd/es/collapse';
import Input from 'antd/es/input';
import List from 'antd/es/list';
import Modal from 'antd/es/modal';
import Row from 'antd/es/row';
import Space from 'antd/es/space';
import Tag from 'antd/es/tag';
import Tooltip from 'antd/es/tooltip';
import Typography from 'antd/es/typography';
import DislikeOutlined from '@ant-design/icons/DislikeOutlined';
import LikeOutlined from '@ant-design/icons/LikeOutlined';
import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { assistantApi, streamChat } from '@/api/endpoints/assistant';
import { queryClient } from '@/app/providers';
import { EmptyState } from '@/components/common/EmptyState';
import { PageHeader } from '@/components/common/PageHeader';
import { ROUTES } from '@/constants/routes';
import type { ChatMessage, Citation, Conversation, PendingAction } from '@/types/assistant';

const QUICK_QUESTIONS = ['门锁没电了怎么办', '七天无理由退货条件', '摄像头陌生人访问怎么处理'];
const DISLIKE_REASONS = [
  { value: 'OFF_TOPIC', label: '答非所问' },
  { value: 'NO_CITATION', label: '缺少引用' },
  { value: 'OUTDATED', label: '内容过时' },
  { value: 'UNSAFE', label: '不安全' },
];

function formatTime(value?: string | null) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

/** 客户对话页：多会话侧栏 + 微信式气泡 + 流式回答 + 引用折叠 + 反馈。 */
export default function ChatPage() {
  const { message } = App.useApp();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState('');
  const [thinking, setThinking] = useState(false);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [failed, setFailed] = useState<{ content: string; code?: string; requestId?: string } | null>(null);
  const [sending, setSending] = useState(false);
  const [feedback, setFeedback] = useState<Record<number, string>>({});
  const [dislikeFor, setDislikeFor] = useState<number | null>(null);
  // 四期：待确认动作（写工具只生成它，确认后才真正提交）
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [acting, setActing] = useState(false);
  // 四期：核验入口（订单号 + 收货手机后四位）；核验后 30 分钟内可查该单
  const [verifyOpen, setVerifyOpen] = useState(false);
  const [verifyForm, setVerifyForm] = useState({ order_no: '', phone_tail: '' });
  const [verified, setVerified] = useState<{ order_no: string; expires_at?: string } | null>(null);
  const [verifying, setVerifying] = useState(false);
  const answerIdRef = useRef<number | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const conversations = useQuery({
    queryKey: ['assistant', 'conversations'],
    queryFn: () => assistantApi.conversations({ page: 1, page_size: 50 }),
  });

  const messages = useQuery({
    queryKey: ['assistant', 'messages', selectedId],
    queryFn: () => assistantApi.messages(selectedId as number, { page: 1, page_size: 100 }),
    enabled: selectedId !== null,
  });

  const create = useMutation({
    mutationFn: () => assistantApi.createConversation(),
    onSuccess: async (data) => {
      setSelectedId(data.id);
      setCitations([]);
      setFailed(null);
      setStreaming('');
      await queryClient.invalidateQueries({ queryKey: ['assistant', 'conversations'] });
    },
    onError: (error) => message.error(String(error)),
  });

  // 默认选中最近一条进行中的会话；没有就保持空态，等用户提问时再建会话
  useEffect(() => {
    const items = conversations.data?.items;
    if (!items || selectedId !== null) return;
    const open = items.find((item) => item.status === 'OPEN');
    if (open) setSelectedId(open.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversations.data, selectedId]);

  const selected = conversations.data?.items.find((item) => item.id === selectedId) ?? null;
  const closed = selected?.status === 'CLOSED';
  const paused = Boolean(selected?.ai_paused);

  // 轮询当前会话：人工回话可在 2 秒内出现在客户端
  useEffect(() => {
    if (selectedId === null || sending) return;
    const timer = window.setInterval(() => {
      void queryClient.invalidateQueries({ queryKey: ['assistant', 'messages', selectedId] });
      void queryClient.invalidateQueries({ queryKey: ['assistant', 'conversations'] });
    }, 2000);
    return () => window.clearInterval(timer);
  }, [selectedId, sending]);
  const items: ChatMessage[] = messages.data?.items ?? [];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [items.length, streaming]);

  const send = async (text: string) => {
    if (!text.trim() || sending || closed) return;
    const content = text.trim();
    setInput('');
    setSending(true);
    setFailed(null);
    setCitations([]);
    setThinking(true);
    setStreaming('');
    let answer = '';
    let conversationId = selectedId;
    try {
      // 第一条消息才创建会话：没有消息的空会话不应该存在
      if (conversationId === null) {
        const created = await assistantApi.createConversation();
        conversationId = created.id;
        setSelectedId(created.id);
      }
      if (paused) {
        // 人工已接管：消息直接发给客服，不走模型
        setThinking(false);
        await assistantApi.customerMessage(conversationId, { content });
        message.success('已发送给人工客服，请等待回复');
        return;
      }
      await streamChat(conversationId, { content, client_msg_id: crypto.randomUUID() }, (event) => {
        if (event.name === 'meta') {
          answerIdRef.current = Number(event.data.message_id ?? 0) || null;
        } else if (event.name === 'delta') {
          setThinking(false);
          answer += event.data.text;
          setStreaming(answer);
        } else if (event.name === 'action') {
          setPending(event.data);
        } else if (event.name === 'citations') {
          setCitations(event.data.hits ?? []);
        } else if (event.name === 'error') {
          setThinking(false);
          setFailed({ content, code: event.data.code, requestId: event.data.request_id });
        }
      });
    } catch (error) {
      setThinking(false);
      const code = (error as Error & { code?: string }).code;
      if (code === 'AI_PAUSED' || code === 'CONVERSATION_CLOSED') {
        message.info(code === 'AI_PAUSED' ? '客服已接管，请等待人工回复' : '该会话已结束，请新开会话');
        await queryClient.invalidateQueries({ queryKey: ['assistant', 'conversations'] });
      } else {
        setFailed({ content, code: (error as Error).message });
      }
    } finally {
      setStreaming('');
      setSending(false);
      if (conversationId !== null) {
        await queryClient.invalidateQueries({ queryKey: ['assistant', 'messages', conversationId] });
      }
      await queryClient.invalidateQueries({ queryKey: ['assistant', 'conversations'] });
    }
  };

  const submitFeedback = (messageId: number, value: string, reason?: string) => {
    assistantApi.submitFeedback(messageId, { value, reason })
      .then(() => setFeedback((prev) => ({ ...prev, [messageId]: value })))
      .catch((error) => message.error('反馈提交失败：' + (error as Error).message));
  };

  const handoff = useMutation({
    mutationFn: () => assistantApi.requestHandoff(selectedId as number),
    onSuccess: async () => {
      message.success('已转人工，请稍候');
      await queryClient.invalidateQueries({ queryKey: ['assistant', 'conversations'] });
    },
    onError: (error) => message.error(String(error)),
  });

  const renderBubble = (item: ChatMessage) => (
    <div key={item.id} style={{ display: 'flex', justifyContent: item.role === 'USER' ? 'flex-end' : 'flex-start', marginBottom: 12 }}>
      <div style={{
        maxWidth: '76%', padding: '8px 12px', borderRadius: 10,
        background: item.role === 'USER' ? '#1F5EFF' : '#fff',
        color: item.role === 'USER' ? '#fff' : 'inherit',
        border: item.role === 'USER' ? 'none' : '1px solid var(--color-border)',
      }}>
        <Typography.Text style={{ color: item.role === 'USER' ? '#fff' : 'inherit', whiteSpace: 'pre-wrap' }}>
          {item.content}
        </Typography.Text>
        {item.role === 'AGENT' ? <Tag color="orange" style={{ marginLeft: 8 }}>人工</Tag> : null}
        {item.role === 'ASSISTANT' && item.id > 0 ? (
          <div style={{ marginTop: 4 }}>
            <Tooltip title="有帮助">
              <Button size="small" type="text" aria-label="有帮助"
                icon={<LikeOutlined style={{ color: feedback[item.id] === 'LIKE' ? '#1F5EFF' : undefined }} />}
                onClick={() => submitFeedback(item.id, 'LIKE')} />
            </Tooltip>
            <Tooltip title="没帮助">
              <Button size="small" type="text" aria-label="没帮助"
                icon={<DislikeOutlined style={{ color: feedback[item.id] === 'DISLIKE' ? '#cf1322' : undefined }} />}
                onClick={() => setDislikeFor(item.id)} />
            </Tooltip>
          </div>
        ) : null}
      </div>
    </div>
  );

  return (
    <div className="qy-page">
      <PageHeader
        title="智能客服"
        subtitle="基于企业知识库回答；答不了可转人工"
        breadcrumb={[{ label: '首页', to: ROUTES.home }, { label: '智能客服' }]}
        extra={(
          <Space>
            <Button onClick={() => create.mutate()} disabled={sending}>新对话</Button>
            <Button
              onClick={() => setVerifyOpen(true)}
              disabled={selectedId === null || sending}
            >
              核验身份
            </Button>
            <Button onClick={() => handoff.mutate()} disabled={selectedId === null}>转人工</Button>
          </Space>
        )}
      />

      <Modal
        open={verifyOpen}
        title="核验身份"
        okText="核验"
        confirmLoading={verifying}
        onCancel={() => setVerifyOpen(false)}
        onOk={async () => {
          if (selectedId === null) return;
          if (verifyForm.phone_tail.length !== 4) {
            message.warning('请填写手机号后四位（4 位数字）');
            return;
          }
          setVerifying(true);
          try {
            const result = await assistantApi.verifyIdentity(selectedId, verifyForm);
            if (result.verified) {
              setVerified({ order_no: verifyForm.order_no, expires_at: result.expires_at });
              message.success('核验通过，30 分钟内可查询该订单');
              setVerifyOpen(false);
            } else {
              message.error(result.message || '核验未通过');
            }
          } catch (error) {
            message.error((error as Error).message || '核验失败');
          } finally {
            setVerifying(false);
          }
        }}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Typography.Text type="secondary">
            订单号与下单手机号后四位必须与订单一致；连续核验失败 3 次会转人工。
          </Typography.Text>
          <Input
            placeholder="订单号，如 QY2026..."
            value={verifyForm.order_no}
            onChange={(event) => setVerifyForm((prev) => ({ ...prev, order_no: event.target.value }))}
          />
          <Input
            placeholder="收货手机号后四位"
            maxLength={4}
            value={verifyForm.phone_tail}
            onChange={(event) => setVerifyForm((prev) => ({ ...prev, phone_tail: event.target.value }))}
          />
        </Space>
      </Modal>

      {verified ? (
        <Typography.Text type="success" style={{ display: 'block', marginBottom: 8 }}>
          已核验订单 {verified.order_no}
          {verified.expires_at ? `（有效期至 ${formatTime(verified.expires_at)}）` : ''}
        </Typography.Text>
      ) : null}

      <Row gutter={12}>
        <Col xs={24} md={8} lg={7}>
          <Card size="small" title={`我的会话（${conversations.data?.total ?? 0}）`} bodyStyle={{ padding: 0 }}>
            <List
              size="small"
              style={{ maxHeight: '58vh', overflowY: 'auto' }}
              dataSource={conversations.data?.items ?? []}
              locale={{ emptyText: <EmptyState title="还没有会话" /> }}
              renderItem={(item: Conversation) => (
                <List.Item
                  onClick={() => { if (!sending) setSelectedId(item.id); }}
                  style={{
                    cursor: sending ? 'not-allowed' : 'pointer',
                    background: item.id === selectedId ? 'var(--color-fill)' : undefined,
                    padding: '8px 12px',
                  }}
                >
                  <Space direction="vertical" size={0} style={{ width: '100%' }}>
                    <Typography.Text ellipsis style={{ maxWidth: 200 }}>
                      {item.title || `会话 #${item.id}`}
                    </Typography.Text>
                    <Space size={6}>
                      <Tag color={item.status === 'OPEN' ? 'blue' : 'default'}>
                        {item.status === 'OPEN' ? '进行中' : '已结束'}
                      </Tag>
                      {item.ai_paused ? <Tag color="orange">人工</Tag> : null}
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        {formatTime(item.last_message_at ?? item.created_at)}
                      </Typography.Text>
                    </Space>
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        </Col>

        <Col xs={24} md={16} lg={17}>
          <Card bodyStyle={{ padding: 0 }}>
            <div style={{ height: '46vh', overflowY: 'auto', padding: 16, background: '#fafafa' }}>
              {items.length === 0 ? (
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <Typography.Text type="secondary">
                    {selectedId === null ? '有什么可以帮你？直接提问即可开始（首次提问会创建新会话）' : '有什么可以帮你？试试：'}
                  </Typography.Text>
                  {QUICK_QUESTIONS.map((question) => (
                    <Button key={question} size="small" onClick={() => setInput(question)}>{question}</Button>
                  ))}
                </Space>
              ) : null}
              {items.map(renderBubble)}
              {thinking ? <Typography.Text type="secondary">正在思考…</Typography.Text> : null}
              {streaming ? (
                <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 12 }}>
                  <div style={{ maxWidth: '76%', padding: '8px 12px', borderRadius: 10, background: '#fff', border: '1px solid var(--color-border)', whiteSpace: 'pre-wrap' }}>
                    {streaming}
                  </div>
                </div>
              ) : null}
              {pending ? (
                <Card size="small" style={{ marginBottom: 12, borderColor: '#faad14' }}>
                  <Space direction="vertical" style={{ width: '100%' }} size={4}>
                    <Typography.Text strong>需要你确认：{pending.summary}</Typography.Text>
                    {pending.impact ? (
                      <Typography.Text type="secondary">{pending.impact}</Typography.Text>
                    ) : null}
                    <Space size={8} wrap>
                      <Tag color={pending.irreversible ? 'red' : 'green'}>
                        {pending.irreversible ? '确认后不可撤销' : '可在售后页撤销'}
                      </Tag>
                      <Typography.Text type="secondary">
                        状态 {pending.status}
                        {pending.expires_at ? ` · 有效期至 ${formatTime(pending.expires_at)}` : ''}
                      </Typography.Text>
                    </Space>
                    {pending.status === 'PROPOSED' ? (
                      <Space>
                        <Button
                          type="primary"
                          loading={acting}
                          onClick={async () => {
                            setActing(true);
                            try {
                              const updated = await assistantApi.confirmAction(pending.id);
                              setPending(updated);
                              message.success('已提交');
                              await messages.refetch();
                            } catch (error) {
                              message.error((error as Error).message || '确认失败');
                            } finally {
                              setActing(false);
                            }
                          }}
                        >
                          确认执行
                        </Button>
                        <Button
                          loading={acting}
                          onClick={async () => {
                            setActing(true);
                            try {
                              const updated = await assistantApi.cancelAction(pending.id);
                              setPending(updated);
                              message.info('已取消，未做任何改动');
                            } catch (error) {
                              message.error((error as Error).message || '取消失败');
                            } finally {
                              setActing(false);
                            }
                          }}
                        >
                          取消
                        </Button>
                      </Space>
                    ) : null}
                  </Space>
                </Card>
              ) : null}
              {citations.length > 0 ? (
                <Collapse
                  size="small"
                  items={[{
                    key: 'citations',
                    label: `引用 ${citations.length} 条`,
                    children: citations.map((cite) => (
                      <div key={`${cite.document_id}-${cite.line_start}`} style={{ marginBottom: 8 }}>
                        <Typography.Text strong>{cite.document_id}</Typography.Text>
                        <Typography.Text type="secondary"> v{cite.version} · L{cite.line_start}-{cite.line_end}</Typography.Text>
                        <div><Typography.Text type="secondary" style={{ fontSize: 12 }}>{cite.title_path}</Typography.Text></div>
                      </div>
                    )),
                  }]}
                />
              ) : null}
              {failed ? (
                <Space direction="vertical" size={4} style={{ marginTop: 8 }}>
                  <Typography.Text type="danger">生成失败{failed.code ? `（${failed.code}）` : ''}</Typography.Text>
                  {failed.requestId ? <Typography.Text type="secondary">request_id: {failed.requestId}</Typography.Text> : null}
                  <Button size="small" onClick={() => send(failed.content)}>重试</Button>
                </Space>
              ) : null}
              <div ref={bottomRef} />
            </div>

            <div style={{ padding: 12, borderTop: '1px solid var(--color-border)' }}>
              {closed ? (
                <Typography.Text type="secondary">该会话已结束，可点「新对话」继续咨询。</Typography.Text>
              ) : (
                <>
                  <Input.TextArea
                    rows={2}
                    value={input}
                    maxLength={2000}
                    showCount
                    disabled={sending}
                    placeholder="输入问题，Enter 发送，Shift+Enter 换行"
                    onChange={(event) => setInput(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                        event.preventDefault();
                        void send(input);
                      }
                    }}
                  />
                  {paused ? (
                    <Typography.Text type="secondary" style={{ display: 'block', marginTop: 6 }}>
                      客服已接管，消息将直接发送给人工客服
                    </Typography.Text>
                  ) : null}
                  <Space style={{ marginTop: 8 }}>
                    <Button type="primary" loading={sending} disabled={!input.trim()} onClick={() => void send(input)}>发送</Button>
                  </Space>
                </>
              )}
            </div>
          </Card>
        </Col>
      </Row>

      <Modal
        open={dislikeFor !== null}
        title="哪里不满意？"
        footer={null}
        onCancel={() => setDislikeFor(null)}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          {DISLIKE_REASONS.map((reason) => (
            <Button key={reason.value} block onClick={() => {
              if (dislikeFor !== null) submitFeedback(dislikeFor, 'DISLIKE', reason.value);
              setDislikeFor(null);
            }}>{reason.label}</Button>
          ))}
        </Space>
      </Modal>
    </div>
  );
}