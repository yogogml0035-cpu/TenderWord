import type { TenderType } from '@/types';
import type { Message, Conversation, DualColumnContent, LogEntry, MessageType } from '@/types/chat';

/**
 * Generate unique conversation ID
 * Format: conv_{timestamp}_{random}
 */
export function generateConversationId(): string {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 8);
  return `conv_${timestamp}_${random}`;
}

/**
 * Generate unique message ID
 * Format: msg_{timestamp}_{random}
 */
export function generateMessageId(): string {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 8);
  return `msg_${timestamp}_${random}`;
}

/**
 * Generate unique log entry ID
 * Format: log_{timestamp}_{random}
 */
export function generateLogEntryId(): string {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 8);
  return `log_${timestamp}_${random}`;
}

/**
 * Format timestamp to readable string
 * @param timestamp - Unix timestamp in milliseconds
 * @returns Formatted string like "14:30" or "昨天 14:30" or "2024-01-15"
 */
export function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp);
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();

  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const isYesterday = date.toDateString() === yesterday.toDateString();

  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  const timeStr = `${hours}:${minutes}`;

  if (isToday) {
    return timeStr;
  }

  if (isYesterday) {
    return `昨天 ${timeStr}`;
  }

  const year = date.getFullYear();
  const month = (date.getMonth() + 1).toString().padStart(2, '0');
  const day = date.getDate().toString().padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Create empty message template
 * @param type - Message type
 * @param conversationId - Parent conversation ID
 * @returns Message object with default values
 */
export function createEmptyMessage(type: MessageType, conversationId: string): Message {
  return {
    id: generateMessageId(),
    type,
    conversationId,
    timestamp: Date.now(),
    status: 'pending',
    content: {
      logs: [],
      aiContent: {
        text: '',
        timestamp: Date.now(),
        isComplete: false,
      },
    },
  };
}

/**
 * Create system message
 * @param content - System message content
 * @param conversationId - Parent conversation ID
 * @returns System message object
 */
export function createSystemMessage(content: string, conversationId: string): Message {
  return {
    id: generateMessageId(),
    type: 'system',
    conversationId,
    timestamp: Date.now(),
    status: 'completed',
    content: {
      logs: [],
      aiContent: {
        text: content,
        timestamp: Date.now(),
        isComplete: true,
      },
    },
  };
}

/**
 * Create empty dual-column content
 * @returns DualColumnContent with empty logs and AI content
 */
export function createEmptyDualColumnContent(): DualColumnContent {
  return {
    logs: [],
    aiContent: {
      text: '',
      timestamp: Date.now(),
      isComplete: false,
    },
  };
}

/**
 * Create new conversation
 * @param title - Conversation title
 * @param tenderType - Tender type ('xjcg' | 'gngk')
 * @returns Conversation object
 */
export function createConversation(title: string, tenderType: TenderType): Conversation {
  return {
    id: generateConversationId(),
    title,
    tenderType,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [],
  };
}

/**
 * Add log entry to dual column content
 * @param content - Current dual column content
 * @param log - Log entry to add
 * @returns Updated dual column content
 */
export function addLogEntry(
  content: DualColumnContent,
  log: Omit<LogEntry, 'id'>
): DualColumnContent {
  const newLog: LogEntry = {
    ...log,
    id: generateLogEntryId(),
  };

  return {
    ...content,
    logs: [...content.logs, newLog],
  };
}

/**
 * Append AI content to dual column content
 * @param content - Current dual column content
 * @param text - Text to append
 * @param isComplete - Whether generation is complete
 * @returns Updated dual column content
 */
export function appendAIContent(
  content: DualColumnContent,
  text: string,
  isComplete: boolean = false
): DualColumnContent {
  return {
    ...content,
    aiContent: {
      ...content.aiContent,
      text: content.aiContent.text + text,
      isComplete,
    },
  };
}

/**
 * Group messages by date
 * @param messages - Array of messages
 * @returns Object with date keys and message arrays
 */
export function groupMessagesByDate(messages: Message[]): Record<string, Message[]> {
  return messages.reduce(
    (groups, message) => {
      const date = new Date(message.timestamp);
      const dateKey = date.toISOString().split('T')[0];

      if (!groups[dateKey]) {
        groups[dateKey] = [];
      }

      groups[dateKey].push(message);
      return groups;
    },
    {} as Record<string, Message[]>
  );
}

/**
 * Get conversation display title
 * @param conversation - Conversation object
 * @returns Display title (uses title or generates one)
 */
export function getConversationDisplayTitle(conversation: Conversation): string {
  if (conversation.title && conversation.title.trim()) {
    return conversation.title;
  }

  const date = new Date(conversation.createdAt);
  const dateStr = date.toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
  });

  return `新对话 ${dateStr}`;
}

/**
 * Truncate text with ellipsis
 * @param text - Text to truncate
 * @param maxLength - Maximum length
 * @returns Truncated text
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }

  return text.substring(0, maxLength - 3) + '...';
}
