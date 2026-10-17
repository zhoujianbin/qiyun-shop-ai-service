import { api, API_BASE } from '../client';
import { tokenStore } from '../tokenStore';
import { newRequestId } from '../requestId';
import type {
  ChatMessage, Citation, Conversation, ConversationPage, Handoff, IdentityResult, MessagePage, StreamEvent,
} from '@/types/assistant';

/** 读取 SSE：fetch + ReadableStream（EventSource 不能带 Authorization）。 */
export async function streamChat(
  conversationId: number,
  body: { content: string; client_msg_id?: string },
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = tokenStore.getAccess();
  const response = await fetch(
    `${API_BASE}/ai/conversations/${conversationId}/messages:stream`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Request-Id': newRequestId(),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
      signal,
    },
  );
  if (!response.ok || !response.body) {
    throw new Error(`流式请求失败：HTTP ${response.status}`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let index = buffer.indexOf('\n\n');
    while (index >= 0) {
      const block = buffer.slice(0, index);
      buffer = buffer.slice(index + 2);
      const name = /^event: (.+)$/m.exec(block)?.[1]?.trim();
      const raw = /^data: (.+)$/m.exec(block)?.[1];
      if (name && raw) {
        try {
          onEvent({ name, data: JSON.parse(raw) } as StreamEvent);
        } catch {
          // 忽略半包
        }
      }
      index = buffer.indexOf('\n\n');
    }
  }
}

export const assistantApi = {
  createConversation: () => api.post<Conversation>('/ai/conversations', {}),
  conversations: (params: Record<string, unknown> = {}) =>
    api.get<ConversationPage>('/ai/conversations', { params }),
  conversation: (id: number | string) => api.get<Conversation>(`/ai/conversations/${id}`),
  closeConversation: (id: number | string) => api.post<Conversation>(`/ai/conversations/${id}/close`),
  messages: (id: number | string, params: Record<string, unknown> = {}) =>
    api.get<MessagePage>(`/ai/conversations/${id}/messages`, { params }),
  verifyIdentity: (id: number | string, body: { order_no: string; phone_tail: string }) =>
    api.post<IdentityResult>(`/ai/conversations/${id}/identity`, body),
  requestHandoff: (id: number | string) => api.post<Handoff>(`/ai/conversations/${id}/handoff`),
  handoffs: (params: Record<string, unknown> = {}) => api.get<Handoff[]>('/ai/handoffs', { params }),
  claimHandoff: (id: number | string) => api.post<Handoff>(`/ai/handoffs/${id}/claim`),
  closeHandoff: (id: number | string, body: { summary: string; back_to_ai?: boolean }) =>
    api.post<Handoff>(`/ai/handoffs/${id}/close`, body),
  agentMessage: (id: number | string, body: { content: string }) =>
    api.post<ChatMessage>(`/ai/conversations/${id}/agent-messages`, body),
  submitFeedback: (messageId: number | string, body: { value: string; reason?: string }) =>
    api.post<Record<string, unknown>>(`/ai/messages/${messageId}/feedback`, body),
  trace: (messageId: number | string) =>
    api.get<Array<Record<string, unknown>>>(`/ai/messages/${messageId}/trace`),
};

export type { Citation };
