/**
 * Unit tests for chat-utils
 */

import {
  generateConversationId,
  generateMessageId,
  generateLogEntryId,
  formatTimestamp,
  createEmptyMessage,
  createSystemMessage,
  createEmptyDualColumnContent,
  createConversation,
  addLogEntry,
  appendAIContent,
  groupMessagesByDate,
  getConversationDisplayTitle,
  truncateText,
  generateConversationTitle,
} from '@/lib/chat-utils';
import { ConversationFactory, MessageFactory } from '../mocks/data-factories';

describe('chat-utils', () => {
  describe('ID Generation', () => {
    describe('generateConversationId', () => {
      it('should generate a conversation ID with correct format', () => {
        const id = generateConversationId();
        expect(id).toMatch(/^conv_\d+_[a-z0-9]{6}$/);
      });

      it('should generate unique IDs', () => {
        const id1 = generateConversationId();
        const id2 = generateConversationId();
        expect(id1).not.toBe(id2);
      });
    });

    describe('generateMessageId', () => {
      it('should generate a message ID with correct format', () => {
        const id = generateMessageId();
        expect(id).toMatch(/^msg_\d+_[a-z0-9]{6}$/);
      });

      it('should generate unique IDs', () => {
        const id1 = generateMessageId();
        const id2 = generateMessageId();
        expect(id1).not.toBe(id2);
      });
    });

    describe('generateLogEntryId', () => {
      it('should generate a log entry ID with correct format', () => {
        const id = generateLogEntryId();
        expect(id).toMatch(/^log_\d+_[a-z0-9]{6}$/);
      });

      it('should generate unique IDs', () => {
        const id1 = generateLogEntryId();
        const id2 = generateLogEntryId();
        expect(id1).not.toBe(id2);
      });
    });
  });

  describe('Timestamp Formatting', () => {
    describe('formatTimestamp', () => {
      it("should format today's timestamp as HH:MM", () => {
        const now = Date.now();
        const formatted = formatTimestamp(now);
        expect(formatted).toMatch(/^\d{2}:\d{2}$/);
      });

      it('should format yesterday\'s timestamp with "昨天" prefix', () => {
        const yesterday = Date.now() - 24 * 60 * 60 * 1000;
        const formatted = formatTimestamp(yesterday);
        expect(formatted).toMatch(/^昨天 \d{2}:\d{2}$/);
      });

      it('should format older dates as YYYY-MM-DD', () => {
        const oldDate = new Date('2024-01-15T10:30:00').getTime();
        const formatted = formatTimestamp(oldDate);
        expect(formatted).toBe('2024-01-15');
      });
    });
  });

  describe('Message Creation', () => {
    describe('createEmptyMessage', () => {
      it('should create a message with default values', () => {
        const conversationId = 'conv_test';
        const message = createEmptyMessage('user', conversationId);

        expect(message.id).toMatch(/^msg_\d+_[a-z0-9]{6}$/);
        expect(message.type).toBe('user');
        expect(message.conversationId).toBe(conversationId);
        expect(message.timestamp).toBeDefined();
        expect(message.status).toBe('pending');
        expect(message.content).toEqual({
          logs: [],
          aiContent: {
            text: '',
            isComplete: false,
            timestamp: expect.any(Number),
          },
        });
      });

      it('should create AI messages', () => {
        const message = createEmptyMessage('ai', 'conv_test');
        expect(message.type).toBe('ai');
      });
    });

    describe('createSystemMessage', () => {
      it('should create a system message with content', () => {
        const content = 'System message';
        const conversationId = 'conv_test';
        const message = createSystemMessage(content, conversationId);

        expect(message.type).toBe('system');
        expect(message.status).toBe('completed');
        expect(message.content).toEqual({
          logs: [],
          aiContent: {
            text: content,
            isComplete: true,
            timestamp: expect.any(Number),
          },
        });
      });
    });
  });

  describe('Dual Column Content', () => {
    describe('createEmptyDualColumnContent', () => {
      it('should create empty dual column content', () => {
        const content = createEmptyDualColumnContent();
        expect(content).toEqual({
          logs: [],
          aiContent: {
            text: '',
            isComplete: false,
            timestamp: expect.any(Number),
          },
        });
      });
    });

    describe('addLogEntry', () => {
      it('should add a log entry to content', () => {
        const content = createEmptyDualColumnContent();
        const logEntry = {
          timestamp: Date.now(),
          level: 'info' as const,
          message: 'Test log',
        };

        const updated = addLogEntry(content, logEntry);

        expect(updated.logs).toHaveLength(1);
        expect(updated.logs[0].message).toBe('Test log');
        expect(updated.logs[0].id).toMatch(/^log_\d+_[a-z0-9]{6}$/);
        expect(updated.aiContent).toEqual(content.aiContent);
      });

      it('should append log entries', () => {
        const content = createEmptyDualColumnContent();
        const log1 = { timestamp: Date.now(), level: 'info' as const, message: 'Log 1' };
        const log2 = { timestamp: Date.now(), level: 'warn' as const, message: 'Log 2' };

        const updated1 = addLogEntry(content, log1);
        const updated2 = addLogEntry(updated1, log2);

        expect(updated2.logs).toHaveLength(2);
        expect(updated2.logs[0].message).toBe('Log 1');
        expect(updated2.logs[1].message).toBe('Log 2');
      });
    });

    describe('appendAIContent', () => {
      it('should append text to AI content', () => {
        const content = createEmptyDualColumnContent();
        const updated = appendAIContent(content, 'Hello ');

        expect(updated.aiContent.text).toBe('Hello ');
        expect(updated.aiContent.isComplete).toBe(false);
      });

      it('should mark content as complete', () => {
        const content = createEmptyDualColumnContent();
        const updated = appendAIContent(content, 'Complete text', true);

        expect(updated.aiContent.text).toBe('Complete text');
        expect(updated.aiContent.isComplete).toBe(true);
      });

      it('should append multiple times', () => {
        const content = createEmptyDualColumnContent();
        const step1 = appendAIContent(content, 'Hello ');
        const step2 = appendAIContent(step1, 'World');

        expect(step2.aiContent.text).toBe('Hello World');
      });
    });
  });

  describe('Conversation Management', () => {
    describe('createConversation', () => {
      it('should create a conversation with correct properties', () => {
        const title = 'Test Conversation';
        const tenderType = 'xjcg';
        const conversation = createConversation(title, tenderType);

        expect(conversation.id).toMatch(/^conv_\d+_[a-z0-9]{6}$/);
        expect(conversation.title).toBe(title);
        expect(conversation.tenderType).toBe(tenderType);
        expect(conversation.messages).toEqual([]);
        expect(conversation.createdAt).toBeDefined();
        expect(conversation.updatedAt).toBeDefined();
      });

      it('should create conversations with different tender types', () => {
        const xjcgConv = createConversation('XJCG Test', 'xjcg');
        const gngkConv = createConversation('GNGK Test', 'gngk');

        expect(xjcgConv.tenderType).toBe('xjcg');
        expect(gngkConv.tenderType).toBe('gngk');
      });
    });

    describe('getConversationDisplayTitle', () => {
      it('should return the title if it exists', () => {
        const conversation = ConversationFactory.create({ title: 'My Conversation' });
        const displayTitle = getConversationDisplayTitle(conversation);
        expect(displayTitle).toBe('My Conversation');
      });

      it('should generate a title if title is empty', () => {
        const conversation = ConversationFactory.create({ title: '' });
        const displayTitle = getConversationDisplayTitle(conversation);
        expect(displayTitle).toMatch(/^新对话 /);
      });

      it('should generate a title if title is whitespace', () => {
        const conversation = ConversationFactory.create({ title: '   ' });
        const displayTitle = getConversationDisplayTitle(conversation);
        expect(displayTitle).toMatch(/^新对话 /);
      });
    });
  });

  describe('Message Grouping', () => {
    describe('groupMessagesByDate', () => {
      it('should group messages by date', () => {
        const date1 = new Date('2024-01-15T10:00:00').getTime();
        const date2 = new Date('2024-01-16T10:00:00').getTime();

        const messages = [
          MessageFactory.create({ timestamp: date1 }),
          MessageFactory.create({ timestamp: date1 + 1000 }),
          MessageFactory.create({ timestamp: date2 }),
        ];

        const groups = groupMessagesByDate(messages);

        expect(Object.keys(groups)).toHaveLength(2);
        expect(groups['2024-01-15']).toHaveLength(2);
        expect(groups['2024-01-16']).toHaveLength(1);
      });

      it('should return empty object for empty array', () => {
        const groups = groupMessagesByDate([]);
        expect(groups).toEqual({});
      });
    });
  });

  describe('Text Utilities', () => {
    describe('truncateText', () => {
      it('should not truncate short text', () => {
        const text = 'Short text';
        const result = truncateText(text, 20);
        expect(result).toBe(text);
      });

      it('should truncate long text with ellipsis', () => {
        const text = 'This is a very long text that needs to be truncated';
        const result = truncateText(text, 20);
        expect(result).toBe('This is a very lo...');
        expect(result.length).toBe(20);
      });

      it('should handle exact length', () => {
        const text = 'Exact length';
        const result = truncateText(text, text.length);
        expect(result).toBe(text);
      });
    });
  });

  describe('generateConversationTitle', () => {
    it('should generate title with correct format', () => {
      const tenderNo = 'ZBGG-2024-001';
      const title = generateConversationTitle(tenderNo);

      // Format: {tenderNo}_{YYYYMMDDhhmm}
      expect(title).toMatch(/^ZBGG-2024-001_\d{12}$/);
    });

    it('should include tender number in title', () => {
      const tenderNo = 'TEST-2024-123';
      const title = generateConversationTitle(tenderNo);

      expect(title.startsWith('TEST-2024-123_')).toBe(true);
    });

    it('should generate timestamp with 12 digits', () => {
      const tenderNo = 'XJCG-001';
      const title = generateConversationTitle(tenderNo);

      const parts = title.split('_');
      expect(parts).toHaveLength(2);
      expect(parts[1]).toMatch(/^\d{12}$/);
    });

    it('should generate different titles at different times', () => {
      // Mock Date to return specific times
      const mockDate1 = new Date('2024-03-15T10:30:00');
      const mockDate2 = new Date('2024-03-15T10:31:00');

      const originalDate = global.Date;
      let dateCallCount = 0;
      global.Date = jest.fn(() => {
        dateCallCount++;
        return dateCallCount === 1 ? mockDate1 : mockDate2;
      }) as unknown as typeof Date;
      Object.setPrototypeOf(global.Date, originalDate);

      const tenderNo = 'SAME-NO';
      const title1 = generateConversationTitle(tenderNo);
      const title2 = generateConversationTitle(tenderNo);

      // Restore Date
      global.Date = originalDate;

      // Titles should be different due to different timestamps
      expect(title1).toBe('SAME-NO_202403151030');
      expect(title2).toBe('SAME-NO_202403151031');
      expect(title1).not.toBe(title2);
    });

    it('should handle tender numbers with special characters', () => {
      const tenderNo = 'TEST_NO-2024.001';
      const title = generateConversationTitle(tenderNo);

      expect(title.startsWith('TEST_NO-2024.001_')).toBe(true);
      expect(title).toMatch(/^TEST_NO-2024\.001_\d{12}$/);
    });
  });
});
