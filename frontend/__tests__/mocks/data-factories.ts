/**
 * Test Data Factories
 * Factory functions for creating test data instances
 */

import type {
  Conversation,
  Message,
  LogEntry,
  DualColumnContent,
  CreateConversationPayload,
  CreateMessagePayload,
} from '@/types/chat';
import type { TaskData, TaskProgress, TaskStatus } from '@/types/api';

/**
 * Generate a unique ID for testing
 */
const generateId = (prefix: string = 'test'): string => {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
};

/**
 * Factory for creating Conversation instances
 */
export class ConversationFactory {
  /**
   * Create a single Conversation instance
   */
  static create(overrides?: Partial<Conversation>): Conversation {
    const now = Date.now();
    const id = generateId('conv');

    return {
      id,
      title: 'Test Conversation',
      tenderType: 'xjcg',
      messages: [],
      createdAt: now,
      updatedAt: now,
      ...overrides,
    };
  }

  /**
   * Create multiple Conversation instances
   */
  static createMany(count: number, overrides?: Partial<Conversation>): Conversation[] {
    return Array.from({ length: count }, (_, i) =>
      this.create({
        title: `Conversation ${i + 1}`,
        ...overrides,
      })
    );
  }

  /**
   * Create a conversation with messages
   */
  static withMessages(
    messageCount: number,
    conversationOverrides?: Partial<Conversation>,
    messageOverrides?: Partial<Message>
  ): Conversation {
    const conversation = this.create(conversationOverrides);
    conversation.messages = MessageFactory.createMany(
      messageCount,
      conversation.id,
      messageOverrides
    );
    return conversation;
  }

  /**
   * Create a conversation from a payload
   */
  static fromPayload(payload: CreateConversationPayload): Conversation {
    const now = Date.now();
    return {
      id: generateId('conv'),
      messages: [],
      createdAt: now,
      updatedAt: now,
      ...payload,
    };
  }
}

/**
 * Factory for creating Message instances
 */
export class MessageFactory {
  /**
   * Create a single Message instance with simple string content
   */
  static create(overrides?: Partial<Message>): Message {
    const now = Date.now();
    const id = generateId('msg');
    const conversationId = overrides?.conversationId || generateId('conv');

    return {
      id,
      conversationId,
      type: 'user',
      content: 'Test message content',
      timestamp: now,
      status: 'sent',
      ...overrides,
    };
  }

  /**
   * Create a Message with dual-column content
   */
  static createDualColumn(
    overrides?: Partial<Omit<Message, 'content'>> & {
      content?: Partial<DualColumnContent>;
    }
  ): Message {
    const now = Date.now();
    const id = generateId('msg');
    const conversationId = overrides?.conversationId || generateId('conv');
    const { content: contentOverrides, ...messageOverrides } = overrides || {};

    const dualContent: DualColumnContent = {
      logs: [
        LogEntryFactory.create({ timestamp: now }),
        LogEntryFactory.create({ timestamp: now + 100, message: 'Second log entry' }),
      ],
      aiContent: {
        text: 'AI generated content',
        timestamp: now + 200,
        isComplete: false,
      },
      ...contentOverrides,
    };

    return {
      id,
      conversationId,
      ...messageOverrides,
      type: 'ai',
      content: dualContent,
      timestamp: now,
      status: 'generating',
    };
  }

  /**
   * Create multiple Message instances
   */
  static createMany(
    count: number,
    conversationId: string,
    overrides?: Partial<Message>
  ): Message[] {
    return Array.from({ length: count }, (_, i) =>
      this.create({
        conversationId,
        content: `Message ${i + 1}`,
        timestamp: Date.now() + i * 100,
        ...overrides,
      })
    );
  }

  /**
   * Create a message from a payload
   */
  static fromPayload(payload: CreateMessagePayload): Message {
    const now = Date.now();
    return {
      id: generateId('msg'),
      timestamp: now,
      ...payload,
    };
  }

  /**
   * Create an AI message with task ID
   */
  static createAIMessage(
    taskId: string,
    conversationId: string,
    overrides?: Partial<Omit<Message, 'content'>> & { content?: Partial<DualColumnContent> }
  ): Message {
    return this.createDualColumn({
      conversationId,
      type: 'ai',
      taskId,
      ...overrides,
    });
  }

  /**
   * Create an error message
   */
  static createErrorMessage(
    conversationId: string,
    error: string,
    overrides?: Partial<Message>
  ): Message {
    return this.create({
      conversationId,
      type: 'system',
      status: 'error',
      error,
      ...overrides,
    });
  }
}

/**
 * Factory for creating LogEntry instances
 */
export class LogEntryFactory {
  /**
   * Create a single LogEntry instance
   */
  static create(overrides?: Partial<LogEntry>): LogEntry {
    const now = Date.now();

    return {
      id: generateId('log'),
      timestamp: now,
      level: 'info',
      message: 'Test log entry',
      ...overrides,
    };
  }

  /**
   * Create multiple LogEntry instances
   */
  static createMany(count: number, overrides?: Partial<LogEntry>): LogEntry[] {
    return Array.from({ length: count }, (_, i) =>
      this.create({
        message: `Log entry ${i + 1}`,
        timestamp: Date.now() + i * 50,
        ...overrides,
      })
    );
  }

  /**
   * Create log entries for different levels
   */
  static createForAllLevels(baseMessage: string = 'Test'): LogEntry[] {
    const levels: Array<'info' | 'warn' | 'error' | 'debug'> = ['info', 'warn', 'error', 'debug'];
    return levels.map((level, i) =>
      this.create({
        level,
        message: `${baseMessage} - ${level.toUpperCase()}`,
        timestamp: Date.now() + i * 100,
      })
    );
  }
}

/**
 * Factory for creating TaskData instances
 */
export class TaskFactory {
  /**
   * Create a single TaskData instance
   */
  static create(overrides?: Partial<TaskData>): TaskData {
    const now = new Date();
    const progress: TaskProgress = {
      completed_nodes: [],
      running_nodes: [],
      completed_count: 0,
      total_nodes: 6,
      progress_percent: 0,
    };

    return {
      task_id: generateId('task'),
      status: 'queued' as TaskStatus,
      created_at: now.toISOString(),
      progress,
      ...overrides,
    };
  }

  /**
   * Create a running task with progress
   */
  static createRunning(overrides?: Partial<TaskData>): TaskData {
    return this.create({
      status: 'running',
      started_at: new Date().toISOString(),
      progress: {
        completed_nodes: ['prepare_template', 'extract_tender_params'],
        running_nodes: ['delete_tender_param'],
        completed_count: 2,
        total_nodes: 6,
        progress_percent: 33,
      },
      ...overrides,
    });
  }

  /**
   * Create a completed task
   */
  static createCompleted(overrides?: Partial<TaskData>): TaskData {
    const startTime = Date.now() - 60000; // 1 minute ago

    return this.create({
      status: 'completed',
      started_at: new Date(startTime).toISOString(),
      completed_at: new Date().toISOString(),
      elapsed_seconds: 60,
      progress: {
        completed_nodes: [
          'prepare_template',
          'extract_tender_params',
          'delete_tender_param',
          'get_replacements',
          'replace_content',
          'update_word',
        ],
        running_nodes: [],
        completed_count: 6,
        total_nodes: 6,
        progress_percent: 100,
      },
      result: {
        output_file: '/output/test-file.docx',
        file_name: 'test-file.docx',
        file_size: 102400,
        model_used: 'deepseek',
        total_time_seconds: 60,
      },
      ...overrides,
    });
  }

  /**
   * Create a failed task
   */
  static createFailed(overrides?: Partial<TaskData>): TaskData {
    return this.create({
      status: 'failed',
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      ...overrides,
    });
  }

  /**
   * Create multiple TaskData instances
   */
  static createMany(count: number, overrides?: Partial<TaskData>): TaskData[] {
    return Array.from({ length: count }, (_, i) =>
      this.create({
        task_id: `task_${i + 1}`,
        ...overrides,
      })
    );
  }
}

/**
 * Factory for creating DualColumnContent instances
 */
export class DualColumnContentFactory {
  /**
   * Create a dual column content with logs and AI content
   */
  static create(overrides?: Partial<DualColumnContent>): DualColumnContent {
    const now = Date.now();

    return {
      logs: LogEntryFactory.createMany(3),
      aiContent: {
        text: 'AI generated content',
        timestamp: now,
        isComplete: false,
      },
      ...overrides,
    };
  }

  /**
   * Create completed dual column content
   */
  static createCompleted(text: string = 'Completed content'): DualColumnContent {
    return this.create({
      aiContent: {
        text,
        timestamp: Date.now(),
        isComplete: true,
      },
    });
  }

  /**
   * Create empty dual column content
   */
  static createEmpty(): DualColumnContent {
    return {
      logs: [],
      aiContent: {
        text: '',
        timestamp: Date.now(),
        isComplete: false,
      },
    };
  }
}
