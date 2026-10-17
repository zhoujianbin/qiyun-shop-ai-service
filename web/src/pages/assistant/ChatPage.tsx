import App from 'antd/es/app';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Collapse from 'antd/es/collapse';
import Input from 'antd/es/input';
import Modal from 'antd/es/modal';
import Space from 'antd/es/space';
import Tag from 'antd/es/tag';
import Tooltip from 'antd/es/tooltip';
import Typography from 'antd/es/typography';
import DislikeOutlined from '@ant-design/icons/DislikeOutlined';
import LikeOutlined from '@ant-design/icons/LikeOutlined';
import { useEffect, useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { assistantApi, streamChat } from '@/api/endpoints/assistant';
import { PageHeader } from '@/components/common/PageHeader';
import { ROUTES } from '@/constants/routes';
import type { ChatMessage, Citation, Conversation } from '@/types/assistant';

const QUICK_QUESTIONS = ['门锁没电了怎么办', '七天无理由退货条件', '摄像头陌生人访问怎么处理'];

const DISLIKE_REASONS = [
  { value: 'OFF_TOPIC', label: '答非所问' },
  { value: 'NO_CITATION', label: '缺少引用' },
  { value: 'OUTDATED', label: '内容过时' },
  { value: 'UNSAFE', label: '不安全' },
];

/** 客户对话页：微信式气泡、思考态→流式、引用折叠、快捷问题、失败重试。 */
export default function ChatPage() {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState('');
  const [thinking, setThinking] = useState(false);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [failed, setFailed] = useState<{ content: string; code?: string; requestId?: string } | null>(null);
  const [sending, setSending] = useState(false);
  const [feedback, setFeedback] = useState<Record<number, string>>({});
  const [dislikeFor, setDislikeFor] = useState<number | null>(null);
  const answerIdRef = useRef<number | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const create = useMutation({
    mutationFn: () => assistantApi.createConversation(),
    onSuccess: (data) => setConversation(data),
    onError: (error) => message.error(String(error)),
  });

  useEffect(() => {
    if (!conversation) create.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streaming]);

  const send = async (text: string) => {
    if (!conversation || !text.trim() || sending) return;
    const content = text.trim();
    setInput('');
    setSending(true);
    setFailed(null);
    setCitations([]);
    setThinking(true);
    setStreaming('');
    setMessages((prev) => [...prev, {
      id: -Date.now(), seq: prev.length + 1, role: 'USER', content, status: 'DONE',
    }]);

    const clientMsgId = crypto.randomUUID();
    let answer = '';
    try {
      await streamChat(conversation.id, { content, client_msg_id: clientMsgId }, (event) => {
        if (event.name === 'meta') {
          answerIdRef.current = Number(event.data.message_id ?? 0) || null;
        } else if (event.name === 'delta') {
          setThinking(false);
          answer += event.data.text;
          setStreaming(answer);
        } else if (event.name === 'citations') {
          setCitations(event.data.hits ?? []);
        } else if (event.name === 'error') {
          setThinking(false);
          setFailed({ content, code: event.data.code, requestId: event.data.request_id });
        }
      });
      if (answer) {
        setMessages((prev) => [...prev, {
          id: answerIdRef.current ?? -Date.now(), seq: prev.length + 2,
          role: 'ASSISTANT', content: answer, status: 'DONE',
        }]);
      }
    } catch (error) {
      setThinking(false);
      setFailed({ content, code: (error as Error).message });
    } finally {
      setStreaming('');
      setSending(false);
      await queryClient.invalidateQueries({ queryKey: ['assistant'] });
    }
  };

  const submitFeedback = (messageId: number, value: string, reason?: string) => {
    assistantApi.submitFeedback(messageId, { value, reason })
      .then(() => setFeedback((prev) => ({ ...prev, [messageId]: value })))
      .catch((error) => message.error(`反馈提交失败：${(error as Error).message}`));
  };

  const handoff = useMutation({
    mutationFn: () => assistantApi.requestHandoff(conversation!.id),
    onSuccess: () => message.success('已转人工，请稍候'),
    onError: (error) => message.error(String(error)),
  });

  return (
    <div className="qy-page">
      <PageHeader
        title="智能客服"
        subtitle="基于企业知识库回答；答不了可转人工"
        breadcrumb={[{ label: '首页', to: ROUTES.home }, { label: '智能客服' }]}
        extra={<Button onClick={() => handoff.mutate()} disabled={!conversation}>转人工</Button>}
      />

      <Card bodyStyle={{ padding: 0 }}>
        <div style={{ height: '58vh', overflowY: 'auto', padding: 16, background: '#fafafa' }}>
          {messages.length === 0 ? (
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <Typography.Text type="secondary">有什么可以帮你？试试：</Typography.Text>
              {QUICK_QUESTIONS.map((question) => (
                <Button key={question} size="small" onClick={() => setInput(question)}>{question}</Button>
              ))}
            </Space>
          ) : null}

          {messages.map((item) => (
            <div key={item.id} style={{ display: 'flex', justifyContent: item.role === 'USER' ? 'flex-end' : 'flex-start', marginBottom: 12 }}>
              <div style={{
                maxWidth: '72%', padding: '8px 12px', borderRadius: 10,
                background: item.role === 'USER' ? '#1F5EFF' : '#fff',
                color: item.role === 'USER' ? '#fff' : 'inherit',
                border: item.role === 'USER' ? 'none' : '1px solid var(--color-border)',
              }}>
                <Typography.Text style={{ color: item.role === 'USER' ? '#fff' : 'inherit' }}>{item.content}</Typography.Text>
                {item.role === 'AGENT' ? <Tag color="orange" style={{ marginLeft: 8 }}>人工</Tag> : null}
                {item.role === 'ASSISTANT' && item.id > 0 ? (
                  <div style={{ marginTop: 4 }}>
                    <Tooltip title="有帮助">
                      <Button
                        size="small" type="text" aria-label="有帮助"
                        icon={<LikeOutlined style={{ color: feedback[item.id] === 'LIKE' ? '#1F5EFF' : undefined }} />}
                        onClick={() => submitFeedback(item.id, 'LIKE')}
                      />
                    </Tooltip>
                    <Tooltip title="没帮助">
                      <Button
                        size="small" type="text" aria-label="没帮助"
                        icon={<DislikeOutlined style={{ color: feedback[item.id] === 'DISLIKE' ? '#cf1322' : undefined }} />}
                        onClick={() => setDislikeFor(item.id)}
                      />
                    </Tooltip>
                  </div>
                ) : null}
              </div>
            </div>
          ))}

          {thinking ? <Typography.Text type="secondary">正在思考…</Typography.Text> : null}
          {streaming ? (
            <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 12 }}>
              <div style={{ maxWidth: '72%', padding: '8px 12px', borderRadius: 10, background: '#fff', border: '1px solid var(--color-border)' }}>
                {streaming}
              </div>
            </div>
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
          <Modal
            open={dislikeFor !== null}
            title="哪里不满意？"
            footer={null}
            onCancel={() => setDislikeFor(null)}
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              {DISLIKE_REASONS.map((reason) => (
                <Button
                  key={reason.value}
                  block
                  onClick={() => {
                    if (dislikeFor !== null) submitFeedback(dislikeFor, 'DISLIKE', reason.value);
                    setDislikeFor(null);
                  }}
                >
                  {reason.label}
                </Button>
              ))}
            </Space>
          </Modal>
          <div ref={bottomRef} />
        </div>

        <div style={{ padding: 12, borderTop: '1px solid var(--color-border)' }}>
          <Input.TextArea
            rows={2}
            value={input}
            maxLength={2000}
            showCount
            disabled={sending || !conversation}
            placeholder="输入问题，Enter 发送，Shift+Enter 换行"
            onChange={(event) => setInput(event.target.value)}
            onPressEnter={(event) => {
              if (!event.shiftKey) {
                event.preventDefault();
                void send(input);
              }
            }}
          />
          <Space style={{ marginTop: 8 }}>
            <Button type="primary" loading={sending} disabled={!input.trim()} onClick={() => void send(input)}>发送</Button>
          </Space>
        </div>
      </Card>
    </div>
  );
}
