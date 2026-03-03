"use strict";
/**
 * Unit tests for chat-utils
 */
Object.defineProperty(exports, "__esModule", { value: true });
var chat_utils_1 = require("@/lib/chat-utils");
var data_factories_1 = require("../mocks/data-factories");
describe('chat-utils', function () {
    describe('ID Generation', function () {
        describe('generateConversationId', function () {
            it('should generate a conversation ID with correct format', function () {
                var id = (0, chat_utils_1.generateConversationId)();
                expect(id).toMatch(/^conv_\d+_[a-z0-9]{6}$/);
            });
            it('should generate unique IDs', function () {
                var id1 = (0, chat_utils_1.generateConversationId)();
                var id2 = (0, chat_utils_1.generateConversationId)();
                expect(id1).not.toBe(id2);
            });
        });
        describe('generateMessageId', function () {
            it('should generate a message ID with correct format', function () {
                var id = (0, chat_utils_1.generateMessageId)();
                expect(id).toMatch(/^msg_\d+_[a-z0-9]{6}$/);
            });
            it('should generate unique IDs', function () {
                var id1 = (0, chat_utils_1.generateMessageId)();
                var id2 = (0, chat_utils_1.generateMessageId)();
                expect(id1).not.toBe(id2);
            });
        });
        describe('generateLogEntryId', function () {
            it('should generate a log entry ID with correct format', function () {
                var id = (0, chat_utils_1.generateLogEntryId)();
                expect(id).toMatch(/^log_\d+_[a-z0-9]{6}$/);
            });
            it('should generate unique IDs', function () {
                var id1 = (0, chat_utils_1.generateLogEntryId)();
                var id2 = (0, chat_utils_1.generateLogEntryId)();
                expect(id1).not.toBe(id2);
            });
        });
    });
    describe('Timestamp Formatting', function () {
        describe('formatTimestamp', function () {
            it('should format today\'s timestamp as HH:MM', function () {
                var now = Date.now();
                var formatted = (0, chat_utils_1.formatTimestamp)(now);
                expect(formatted).toMatch(/^\d{2}:\d{2}$/);
            });
            it('should format yesterday\'s timestamp with "昨天" prefix', function () {
                var yesterday = Date.now() - 24 * 60 * 60 * 1000;
                var formatted = (0, chat_utils_1.formatTimestamp)(yesterday);
                expect(formatted).toMatch(/^昨天 \d{2}:\d{2}$/);
            });
            it('should format older dates as YYYY-MM-DD', function () {
                var oldDate = new Date('2024-01-15T10:30:00').getTime();
                var formatted = (0, chat_utils_1.formatTimestamp)(oldDate);
                expect(formatted).toBe('2024-01-15');
            });
        });
    });
    describe('Message Creation', function () {
        describe('createEmptyMessage', function () {
            it('should create a message with default values', function () {
                var conversationId = 'conv_test';
                var message = (0, chat_utils_1.createEmptyMessage)('user', conversationId);
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
                it('should create AI messages', function () {
                    var message = (0, chat_utils_1.createEmptyMessage)('ai', 'conv_test');
                    expect(message.type).toBe('ai');
                });
            });
            describe('createSystemMessage', function () {
                it('should create a system message with content', function () {
                    var content = 'System message';
                    var conversationId = 'conv_test';
                    var message = (0, chat_utils_1.createSystemMessage)(content, conversationId);
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
            describe('Dual Column Content', function () {
                describe('createEmptyDualColumnContent', function () {
                    it('should create empty dual column content', function () {
                        var content = (0, chat_utils_1.createEmptyDualColumnContent)();
                        expect(content).toEqual({
                            logs: [],
                            aiContent: {
                                text: '',
                                isComplete: false,
                                timestamp: expect.any(Number),
                            },
                        });
                    });
                    describe('addLogEntry', function () {
                        it('should add a log entry to content', function () {
                            var content = (0, chat_utils_1.createEmptyDualColumnContent)();
                            var logEntry = {
                                timestamp: Date.now(),
                                level: 'info',
                                message: 'Test log',
                            };
                            var updated = (0, chat_utils_1.addLogEntry)(content, logEntry);
                            expect(updated.logs).toHaveLength(1);
                            expect(updated.logs[0].message).toBe('Test log');
                            expect(updated.logs[0].id).toMatch(/^log_\d+_[a-z0-9]{6}$/);
                            expect(updated.aiContent).toEqual(content.aiContent);
                        });
                        it('should append log entries', function () {
                            var content = (0, chat_utils_1.createEmptyDualColumnContent)();
                            var log1 = { timestamp: Date.now(), level: 'info', message: 'Log 1' };
                            var log2 = { timestamp: Date.now(), level: 'warn', message: 'Log 2' };
                            var updated1 = (0, chat_utils_1.addLogEntry)(content, log1);
                            var updated2 = (0, chat_utils_1.addLogEntry)(updated1, log2);
                            expect(updated2.logs).toHaveLength(2);
                            expect(updated2.logs[0].message).toBe('Log 1');
                            expect(updated2.logs[1].message).toBe('Log 2');
                        });
                    });
                    describe('appendAIContent', function () {
                        it('should append text to AI content', function () {
                            var content = (0, chat_utils_1.createEmptyDualColumnContent)();
                            var updated = (0, chat_utils_1.appendAIContent)(content, 'Hello ');
                            expect(updated.aiContent.text).toBe('Hello ');
                            expect(updated.aiContent.isComplete).toBe(false);
                        });
                        it('should mark content as complete', function () {
                            var content = (0, chat_utils_1.createEmptyDualColumnContent)();
                            var updated = (0, chat_utils_1.appendAIContent)(content, 'Complete text', true);
                            expect(updated.aiContent.text).toBe('Complete text');
                            expect(updated.aiContent.isComplete).toBe(true);
                        });
                        it('should append multiple times', function () {
                            var content = (0, chat_utils_1.createEmptyDualColumnContent)();
                            var step1 = (0, chat_utils_1.appendAIContent)(content, 'Hello ');
                            var step2 = (0, chat_utils_1.appendAIContent)(step1, 'World');
                            expect(step2.aiContent.text).toBe('Hello World');
                        });
                    });
                });
                describe('Conversation Management', function () {
                    describe('createConversation', function () {
                        it('should create a conversation with correct properties', function () {
                            var title = 'Test Conversation';
                            var tenderType = 'xjcg';
                            var conversation = (0, chat_utils_1.createConversation)(title, tenderType);
                            expect(conversation.id).toMatch(/^conv_\d+_[a-z0-9]{6}$/);
                            expect(conversation.title).toBe(title);
                            expect(conversation.tenderType).toBe(tenderType);
                            expect(conversation.messages).toEqual([]);
                            expect(conversation.createdAt).toBeDefined();
                            expect(conversation.updatedAt).toBeDefined();
                        });
                        it('should create conversations with different tender types', function () {
                            var xjcgConv = (0, chat_utils_1.createConversation)('XJCG Test', 'xjcg');
                            var gngkConv = (0, chat_utils_1.createConversation)('GNGK Test', 'gngk');
                            expect(xjcgConv.tenderType).toBe('xjcg');
                            expect(gngkConv.tenderType).toBe('gngk');
                        });
                    });
                    describe('getConversationDisplayTitle', function () {
                        it('should return the title if it exists', function () {
                            var conversation = data_factories_1.ConversationFactory.create({ title: 'My Conversation' });
                            var displayTitle = (0, chat_utils_1.getConversationDisplayTitle)(conversation);
                            expect(displayTitle).toBe('My Conversation');
                        });
                        it('should generate a title if title is empty', function () {
                            var conversation = data_factories_1.ConversationFactory.create({ title: '' });
                            var displayTitle = (0, chat_utils_1.getConversationDisplayTitle)(conversation);
                            expect(displayTitle).toMatch(/^新对话 /);
                        });
                        it('should generate a title if title is whitespace', function () {
                            var conversation = data_factories_1.ConversationFactory.create({ title: '   ' });
                            var displayTitle = (0, chat_utils_1.getConversationDisplayTitle)(conversation);
                            expect(displayTitle).toMatch(/^新对话 /);
                        });
                    });
                });
                describe('Message Grouping', function () {
                    describe('groupMessagesByDate', function () {
                        it('should group messages by date', function () {
                            var date1 = new Date('2024-01-15T10:00:00').getTime();
                            var date2 = new Date('2024-01-16T10:00:00').getTime();
                            var messages = [
                                data_factories_1.MessageFactory.create({ timestamp: date1 }),
                                data_factories_1.MessageFactory.create({ timestamp: date1 + 1000 }),
                                data_factories_1.MessageFactory.create({ timestamp: date2 }),
                            ];
                            var groups = (0, chat_utils_1.groupMessagesByDate)(messages);
                            expect(Object.keys(groups)).toHaveLength(2);
                            expect(groups['2024-01-15']).toHaveLength(2);
                            expect(groups['2024-01-16']).toHaveLength(1);
                        });
                        it('should return empty object for empty array', function () {
                            var groups = (0, chat_utils_1.groupMessagesByDate)([]);
                            expect(groups).toEqual({});
                        });
                    });
                });
                describe('Text Utilities', function () {
                    describe('truncateText', function () {
                        it('should not truncate short text', function () {
                            var text = 'Short text';
                            var result = (0, chat_utils_1.truncateText)(text, 20);
                            expect(result).toBe(text);
                        });
                        it('should truncate long text with ellipsis', function () {
                            var text = 'This is a very long text that needs to be truncated';
                            var result = (0, chat_utils_1.truncateText)(text, 20);
                            expect(result).toBe('This is a very lo...');
                            expect(result.length).toBe(20);
                        });
                        it('should handle exact length', function () {
                            var text = 'Exact length';
                            var result = (0, chat_utils_1.truncateText)(text, text.length);
                            expect(result).toBe(text);
                        });
                    });
                });
            });
        });
    });
});
