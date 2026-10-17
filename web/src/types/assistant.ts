/** 三期智能客服类型。 */

export interface Conversation {
  id: number;
  conversation_no: string;
  status: string;
  ai_paused: boolean;
  message_count: number;
  title?: string | null;
  last_message_at?: string | null;
  created_at?: string | null;
}

export interface ConversationPage {
  page: number;
  page_size: number;
  total: number;
  items: Conversation[];
  meta: Record<string, number>;
}

export interface ChatMessage {
  id: number;
  seq: number;
  role: 'USER' | 'ASSISTANT' | 'AGENT' | 'SYSTEM';
  content: string;
  status: string;
  metadata?: Record<string, unknown>;
  created_at?: string | null;
}

export interface MessagePage {
  items: ChatMessage[];
  meta: Record<string, number>;
}

export interface Citation {
  document_id: string;
  version: number;
  title_path: string;
  line_start?: number | null;
  line_end?: number | null;
  snippet?: string;
  entity_tags?: Array<{ type: string; value: string }>;
}

export interface Handoff {
  id: number;
  conversation_id: number;
  reason: string;
  status: string;
  assignee_id?: number | null;
  summary?: string | null;
  created_at?: string | null;
}

export interface IdentityResult {
  verified: boolean;
  message?: string;
  attempts?: number;
  max_attempts?: number;
  expires_at?: string;
  snapshot?: Record<string, string | null>;
}

export type StreamEvent =
  | { name: 'meta'; data: Record<string, unknown> }
  | { name: 'ping'; data: Record<string, unknown> }
  | { name: 'delta'; data: { text: string } }
  | { name: 'citations'; data: { hits: Citation[] } }
  | { name: 'done'; data: Record<string, unknown> }
  | { name: 'error'; data: { code: string; message: string; request_id?: string } };
