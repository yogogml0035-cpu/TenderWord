/**
 * Chat System Type Definitions
 * Chat 系统类型定义
 */

// ============================================
// Message Types
// ============================================

import type { TenderType } from './index';
import type { TaskKind } from './api';

export type MessageType = 'user' | 'ai' | 'system';

export type MessageStatus =
  | 'pending'
  | 'sending'
  | 'sent'
  | 'generating'
  | 'completed'
  | 'error'
  | 'cancelled';

export type TaskMessageKind = 'task-log' | 'task-content' | 'task-download';
export type ChatMessageKind = 'normal' | 'rewrite' | 'task-notice';
export type LocalTaskReason = 'backend_restart';

// ============================================
// Dual Column Content Types
// ============================================

/** Log entry for left column (进度日志) */
export interface LogEntry {
  id: string;
  timestamp: number;
  level: 'info' | 'warn' | 'error' | 'debug';
  message: string;
  node?: string;
}

/** AI content for right column (AI 生成内容) */
export interface AIContent {
  text: string;
  timestamp: number;
  isComplete: boolean;
}

/** Dual column content structure (双列消息内容) */
export interface DualColumnContent {
  logs: LogEntry[];
  aiContent: AIContent;
}

// ============================================
// Message Type
// ============================================

/** Base Message interface */
export interface Message {
  id: string;
  conversationId: string;
  type: MessageType;
  content: string | DualColumnContent;
  timestamp: number;
  status: MessageStatus;
  taskId?: string;
  error?: string;
  metadata?: {
    messageKind?: TaskMessageKind;
    chatKind?: ChatMessageKind;
    chatPrompt?: string;
    chatModel?: 'deepseek' | 'qwen' | 'doubao';
    logs?: LogEntry[];
    outputFile?: string;
    fileName?: string;
    taskKind?: TaskKind;
    progressPercent?: number;
    progressText?: string;
    currentNode?: string;
    currentNodeDisplay?: string;
    lastEventId?: string;
    localTaskReason?: LocalTaskReason;
    [key: string]: unknown;
  };
}

// ============================================
// Conversation Type
// ============================================

/** Conversation interface */
export interface Conversation {
  id: string;
  title: string;
  tenderType: TenderType;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
  currentTaskId?: string;
}

// ============================================
// Chat State Type (for Store)
// ============================================

/** Chat state for Zustand store */
export interface ChatState {
  conversations: Conversation[];
  currentConversationId: string | null;
  isLoading: boolean;
  error: string | null;
}

// ============================================
// Type Guards
// ============================================

/**
 * Check if an object is a valid Message
 */
export function isMessage(obj: unknown): obj is Message {
  if (typeof obj !== 'object' || obj === null) {
    return false;
  }

  const message = obj as Record<string, unknown>;

  return (
    typeof message.id === 'string' &&
    typeof message.conversationId === 'string' &&
    typeof message.type === 'string' &&
    ['user', 'ai', 'system'].includes(message.type) &&
    typeof message.timestamp === 'number' &&
    typeof message.status === 'string' &&
    ['pending', 'sending', 'sent', 'generating', 'completed', 'error', 'cancelled'].includes(
      message.status
    )
  );
}

/**
 * Check if an object is a valid Conversation
 */
export function isConversation(obj: unknown): obj is Conversation {
  if (typeof obj !== 'object' || obj === null) {
    return false;
  }

  const conversation = obj as Record<string, unknown>;

  return (
    typeof conversation.id === 'string' &&
    typeof conversation.title === 'string' &&
    typeof conversation.tenderType === 'string' &&
    ['xjcg', 'gngk', 'gjgk'].includes(conversation.tenderType) &&
    Array.isArray(conversation.messages) &&
    typeof conversation.createdAt === 'number' &&
    typeof conversation.updatedAt === 'number'
  );
}

/**
 * Check if content is DualColumnContent
 */
export function isDualColumnContent(content: unknown): content is DualColumnContent {
  if (typeof content !== 'object' || content === null) {
    return false;
  }

  const dualContent = content as Record<string, unknown>;

  return (
    Array.isArray(dualContent.logs) &&
    typeof dualContent.aiContent === 'object' &&
    dualContent.aiContent !== null &&
    typeof (dualContent.aiContent as Record<string, unknown>).text === 'string' &&
    typeof (dualContent.aiContent as Record<string, unknown>).timestamp === 'number' &&
    typeof (dualContent.aiContent as Record<string, unknown>).isComplete === 'boolean'
  );
}

/**
 * Check if value is a task message kind
 */
export function isTaskMessageKind(value: unknown): value is TaskMessageKind {
  return value === 'task-log' || value === 'task-content' || value === 'task-download';
}

// ============================================
// Utility Types
// ============================================

/** Message creation payload (without auto-generated fields) */
export type CreateMessagePayload = Omit<Message, 'id' | 'timestamp'> & {
  id?: string;
  timestamp?: number;
};

/** Conversation creation payload (without auto-generated fields) */
export type CreateConversationPayload = Omit<
  Conversation,
  'id' | 'messages' | 'createdAt' | 'updatedAt'
> & {
  id?: string;
  messages?: Message[];
  createdAt?: number;
  updatedAt?: number;
};

/** Message update payload (partial) */
export type UpdateMessagePayload = Partial<Omit<Message, 'id' | 'conversationId'>>;

/** Conversation update payload (partial) */
export type UpdateConversationPayload = Partial<Omit<Conversation, 'id' | 'messages'>>;
