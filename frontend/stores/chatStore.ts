import { create } from 'zustand';
import { createJSONStorage, devtools, persist } from 'zustand/middleware';
import type { TenderType } from '@/types';
import {
  isDualColumnContent,
  type Conversation,
  type LogEntry,
  type Message,
  type TaskMessageKind,
} from '@/types/chat';
import { createConversation as createConvUtil, generateMessageId } from '@/lib/chat-utils';

const TASK_LOG_KIND: TaskMessageKind = 'task-log';
const TASK_CONTENT_KIND: TaskMessageKind = 'task-content';
const TASK_DOWNLOAD_KIND: TaskMessageKind = 'task-download';

export interface TaskMessageGroupIds {
  logMessageId?: string;
  contentMessageId?: string;
  downloadMessageId?: string;
}

export interface TaskMessageSnapshot {
  logs?: LogEntry[];
  aiText?: string;
  aiComplete?: boolean;
}

export interface LocatedTaskMessageGroup {
  conversationId: string;
  group: TaskMessageGroupIds;
  logMessage?: Message;
  contentMessage?: Message;
  downloadMessage?: Message;
}

function getTaskMessageKind(message: Message): TaskMessageKind | undefined {
  const kind = message.metadata?.messageKind;
  if (kind === TASK_LOG_KIND || kind === TASK_CONTENT_KIND || kind === TASK_DOWNLOAD_KIND) {
    return kind;
  }
  return undefined;
}

function getMessageById(messages: Message[], messageId?: string): Message | undefined {
  if (!messageId) {
    return undefined;
  }
  return messages.find((message) => message.id === messageId);
}

function buildGroupFromMessages(messages: Message[]): TaskMessageGroupIds {
  const logMessage = messages.find((message) => getTaskMessageKind(message) === TASK_LOG_KIND);
  const contentMessage = messages.find((message) => getTaskMessageKind(message) === TASK_CONTENT_KIND);
  const downloadMessage = messages.find(
    (message) => getTaskMessageKind(message) === TASK_DOWNLOAD_KIND
  );

  if (logMessage || contentMessage || downloadMessage) {
    return {
      ...(logMessage ? { logMessageId: logMessage.id } : {}),
      ...(contentMessage ? { contentMessageId: contentMessage.id } : {}),
      ...(downloadMessage ? { downloadMessageId: downloadMessage.id } : {}),
    };
  }

  const legacyMessage = messages.find(
    (message) => message.type === 'ai' && isDualColumnContent(message.content)
  );

  return legacyMessage ? { contentMessageId: legacyMessage.id } : {};
}

function mergeTaskMessageGroup(
  base: TaskMessageGroupIds,
  next?: TaskMessageGroupIds
): TaskMessageGroupIds {
  if (!next) {
    return base;
  }
  return {
    ...base,
    ...next,
  };
}

interface ChatStore {
  conversations: Conversation[];
  currentConversationId: string | null;
  activeTaskIds: string[];
  taskMessageMap: Record<string, TaskMessageGroupIds>;
  isLoading: boolean;
  error: string | null;
  concurrentTaskWarning: boolean;
  selectedTenderType: TenderType | null;

  createConversation: (tenderno: string, tenderType: TenderType, title?: string) => string;
  updateConversation: (id: string, updates: Partial<Conversation>) => void;
  deleteConversation: (id: string) => void;
  setCurrentConversation: (id: string | null) => void;

  addMessage: (
    conversationId: string,
    message: Omit<Message, 'id' | 'timestamp' | 'conversationId'>
  ) => string;
  updateMessage: (conversationId: string, messageId: string, updates: Partial<Message>) => void;
  deleteMessage: (conversationId: string, messageId: string) => void;

  startTask: (conversationId: string, taskId: string) => TaskMessageGroupIds;
  ensureTaskContentMessage: (
    taskId: string,
    options?: {
      status?: Message['status'];
      content?: string;
      error?: string;
    }
  ) => string | null;
  markTaskContentReady: (taskId: string, aiText?: string) => void;
  completeTask: (
    taskId: string,
    outputFile?: string,
    fileName?: string,
    content?: TaskMessageSnapshot
  ) => void;
  failTask: (taskId: string, error: string, content?: TaskMessageSnapshot) => void;
  cancelTask: (taskId: string, content?: TaskMessageSnapshot) => void;
  discardStaleTask: (taskId: string) => void;

  getCurrentConversation: () => Conversation | null;
  hasActiveTasks: () => boolean;
  clearError: () => void;
  dismissConcurrentWarning: () => void;
  setSelectedTenderType: (type: TenderType | null) => void;
  findConversationByTenderNo: (tenderno: string) => Conversation | null;
  findTaskMessageGroup: (taskId: string) => LocatedTaskMessageGroup | null;
  findMessageByTaskId: (taskId: string) => { conversationId: string; message: Message } | null;
  getSortedConversations: () => Conversation[];
  getMostRecentConversationByType: (type: TenderType) => Conversation | null;
}

export const useChatStore = create<ChatStore>()(
  devtools(
    persist(
      (set, get) => ({
        // State
        conversations: [],
        currentConversationId: null,
        activeTaskIds: [],
        taskMessageMap: {},
        isLoading: false,
        error: null,
        concurrentTaskWarning: false,
        selectedTenderType: null,

        createConversation: (tenderno, tenderType, title) => {
          const conversation = createConvUtil(title || tenderno, tenderType);
          set((state) => ({
            conversations: [conversation, ...state.conversations],
            currentConversationId: conversation.id,
            selectedTenderType: tenderType,
          }));
          return conversation.id;
        },

        updateConversation: (id, updates) => {
          set((state) => ({
            conversations: state.conversations.map((conv) =>
              conv.id === id ? { ...conv, ...updates, updatedAt: Date.now() } : conv
            ),
          }));
        },

        deleteConversation: (id) => {
          set((state) => {
            const conversationToDelete = state.conversations.find((conv) => conv.id === id);
            const deletedTaskIds = new Set(
              (conversationToDelete?.messages || [])
                .map((message) => message.taskId)
                .filter((taskId): taskId is string => typeof taskId === 'string')
            );
            const newConversations = state.conversations.filter((conv) => conv.id !== id);

            let newCurrentId = state.currentConversationId;
            if (state.currentConversationId === id) {
              if (conversationToDelete) {
                const sameTypeConversations = newConversations
                  .filter((conv) => conv.tenderType === conversationToDelete.tenderType)
                  .sort((a, b) => b.createdAt - a.createdAt);
                newCurrentId = sameTypeConversations[0]?.id || null;
              } else {
                newCurrentId = newConversations[0]?.id || null;
              }
            }

            return {
              conversations: newConversations,
              currentConversationId: newCurrentId,
              activeTaskIds: state.activeTaskIds.filter((taskId) => !deletedTaskIds.has(taskId)),
              taskMessageMap: Object.fromEntries(
                Object.entries(state.taskMessageMap).filter(([taskId]) => !deletedTaskIds.has(taskId))
              ),
            };
          });
        },

        setCurrentConversation: (id) => set({ currentConversationId: id }),

        addMessage: (conversationId, message) => {
          const newMessage = {
            ...message,
            conversationId,
            id: generateMessageId(),
            timestamp: Date.now(),
          };
          set((state) => ({
            conversations: state.conversations.map((conv) =>
              conv.id === conversationId
                ? { ...conv, messages: [...conv.messages, newMessage], updatedAt: Date.now() }
                : conv
            ),
          }));
          return newMessage.id;
        },

        updateMessage: (conversationId, messageId, updates) => {
          set((state) => ({
            conversations: state.conversations.map((conv) =>
              conv.id === conversationId
                ? {
                    ...conv,
                    messages: conv.messages.map((msg) =>
                      msg.id === messageId
                        ? {
                            ...msg,
                            ...updates,
                            ...(updates.metadata
                              ? { metadata: { ...(msg.metadata || {}), ...updates.metadata } }
                              : {}),
                          }
                        : msg
                    ),
                    updatedAt: Date.now(),
                  }
                : conv
            ),
          }));
        },

        deleteMessage: (conversationId, messageId) => {
          set((state) => ({
            conversations: state.conversations.map((conv) =>
              conv.id === conversationId
                ? {
                    ...conv,
                    messages: conv.messages.filter((msg) => msg.id !== messageId),
                    updatedAt: Date.now(),
                  }
                : conv
            ),
          }));
        },

        startTask: (conversationId, taskId) => {
          const state = get();
          const hasGeneratingMessage = state.conversations.some((conversation) =>
            conversation.messages.some((message) => message.status === 'generating')
          );
          if (state.activeTaskIds.length > 0 || hasGeneratingMessage) {
            set({ concurrentTaskWarning: true });
          }

          const logMessageId = get().addMessage(conversationId, {
            type: 'ai',
            content: '',
            status: 'generating',
            taskId,
            metadata: {
              messageKind: TASK_LOG_KIND,
              logs: [],
            },
          });

          const group = { logMessageId };

          set((currentState) => ({
            activeTaskIds: currentState.activeTaskIds.includes(taskId)
              ? currentState.activeTaskIds
              : [...currentState.activeTaskIds, taskId],
            taskMessageMap: {
              ...currentState.taskMessageMap,
              [taskId]: group,
            },
          }));

          return group;
        },

        ensureTaskContentMessage: (taskId, options) => {
          const locatedTaskGroup = get().findTaskMessageGroup(taskId);
          if (!locatedTaskGroup) {
            return null;
          }

          if (locatedTaskGroup.contentMessage) {
            return locatedTaskGroup.contentMessage.id;
          }

          const contentMessageId = get().addMessage(locatedTaskGroup.conversationId, {
            type: 'ai',
            content: options?.content || '',
            status: options?.status || 'generating',
            ...(typeof options?.error === 'string' ? { error: options.error } : {}),
            taskId,
            metadata: {
              messageKind: TASK_CONTENT_KIND,
            },
          });

          const nextGroup = mergeTaskMessageGroup(locatedTaskGroup.group, { contentMessageId });
          set((state) => ({
            taskMessageMap: {
              ...state.taskMessageMap,
              [taskId]: nextGroup,
            },
          }));

          return contentMessageId;
        },

        markTaskContentReady: (taskId, aiText) => {
          const locatedTaskGroup = get().findTaskMessageGroup(taskId);
          if (!locatedTaskGroup) {
            return;
          }

          const nextText = typeof aiText === 'string' ? aiText : undefined;
          const { conversationId, contentMessage } = locatedTaskGroup;

          if (!contentMessage) {
            get().ensureTaskContentMessage(taskId, {
              status: 'completed',
              ...(typeof nextText === 'string' ? { content: nextText } : {}),
            });
            return;
          }

          if (contentMessage.status !== 'generating') {
            return;
          }

          get().updateMessage(conversationId, contentMessage.id, {
            status: 'completed',
            error: undefined,
            ...(typeof nextText === 'string' ? { content: nextText } : {}),
            metadata: {
              messageKind: TASK_CONTENT_KIND,
            },
          });
        },

        completeTask: (taskId, outputFile, fileName, content) => {
          const locatedTaskGroup = get().findTaskMessageGroup(taskId);
          let nextGroup: TaskMessageGroupIds | undefined;

          if (locatedTaskGroup) {
            const { conversationId, logMessage, contentMessage, downloadMessage, group } =
              locatedTaskGroup;
            const hasLogs = Array.isArray(content?.logs);
            const hasAiText = typeof content?.aiText === 'string';
            const hasNonEmptyAiText = hasAiText && (content?.aiText?.length || 0) > 0;

            if (logMessage) {
              get().updateMessage(conversationId, logMessage.id, {
                status: 'completed',
                metadata: {
                  messageKind: TASK_LOG_KIND,
                  ...(hasLogs ? { logs: content?.logs } : {}),
                },
              });
            }

            let contentMessageId: string | undefined = contentMessage?.id;
            if (!contentMessage && hasNonEmptyAiText) {
              contentMessageId =
                get().ensureTaskContentMessage(taskId, {
                  status: 'completed',
                  content: content?.aiText || '',
                }) || undefined;
            } else if (contentMessage) {
              get().updateMessage(conversationId, contentMessage.id, {
                status: 'completed',
                ...(hasAiText ? { content: content?.aiText || '' } : {}),
                error: undefined,
                metadata: {
                  messageKind: TASK_CONTENT_KIND,
                },
              });
            }

            let downloadMessageId = group.downloadMessageId;
            if (typeof outputFile === 'string' && outputFile.length > 0) {
              const resolvedFileName =
                typeof fileName === 'string' && fileName.length > 0
                  ? fileName
                  : outputFile.split(/[\\/]/).pop();

              if (downloadMessage) {
                get().updateMessage(conversationId, downloadMessage.id, {
                  status: 'completed',
                  content: resolvedFileName || '下载生成文件',
                  metadata: {
                    messageKind: TASK_DOWNLOAD_KIND,
                    outputFile,
                    fileName: resolvedFileName,
                  },
                });
                downloadMessageId = downloadMessage.id;
              } else {
                downloadMessageId = get().addMessage(conversationId, {
                  type: 'ai',
                  content: resolvedFileName || '下载生成文件',
                  status: 'completed',
                  taskId,
                  metadata: {
                    messageKind: TASK_DOWNLOAD_KIND,
                    outputFile,
                    fileName: resolvedFileName,
                  },
                });
              }
            }

            nextGroup = mergeTaskMessageGroup(group, {
              ...(logMessage ? { logMessageId: logMessage.id } : {}),
              ...(contentMessageId ? { contentMessageId } : {}),
              ...(downloadMessageId ? { downloadMessageId } : {}),
            });
          }

          set((state) => {
            const nextTaskMessageMap = { ...state.taskMessageMap };
            if (nextGroup) {
              nextTaskMessageMap[taskId] = nextGroup;
            } else {
              delete nextTaskMessageMap[taskId];
            }

            return {
              activeTaskIds: state.activeTaskIds.filter((id) => id !== taskId),
              taskMessageMap: nextTaskMessageMap,
            };
          });
        },

        failTask: (taskId, error, content) => {
          const locatedTaskGroup = get().findTaskMessageGroup(taskId);
          let nextGroup: TaskMessageGroupIds | undefined;

          if (locatedTaskGroup) {
            const { conversationId, logMessage, contentMessage, group } = locatedTaskGroup;
            const hasLogs = Array.isArray(content?.logs);
            const hasAiText = typeof content?.aiText === 'string';
            const hasNonEmptyAiText = hasAiText && (content?.aiText?.length || 0) > 0;

            if (logMessage && getTaskMessageKind(logMessage) === TASK_LOG_KIND) {
              get().updateMessage(conversationId, logMessage.id, {
                status: 'error',
                metadata: {
                  messageKind: TASK_LOG_KIND,
                  ...(hasLogs ? { logs: content?.logs } : {}),
                },
              });
            }

            let contentMessageId: string | undefined = contentMessage?.id;
            if (!contentMessage && hasNonEmptyAiText) {
              contentMessageId =
                get().ensureTaskContentMessage(taskId, {
                  status: 'error',
                  content: content?.aiText || '',
                  error,
                }) || undefined;
            } else if (contentMessage) {
              get().updateMessage(conversationId, contentMessage.id, {
                status: 'error',
                error,
                ...(hasAiText ? { content: content?.aiText || '' } : {}),
                metadata: {
                  messageKind: TASK_CONTENT_KIND,
                },
              });
            }

            nextGroup = mergeTaskMessageGroup(group, {
              ...(logMessage ? { logMessageId: logMessage.id } : {}),
              ...(contentMessageId ? { contentMessageId } : {}),
            });
          }

          set((state) => {
            const nextTaskMessageMap = { ...state.taskMessageMap };
            if (nextGroup) {
              nextTaskMessageMap[taskId] = nextGroup;
            } else {
              delete nextTaskMessageMap[taskId];
            }

            return {
              activeTaskIds: state.activeTaskIds.filter((id) => id !== taskId),
              taskMessageMap: nextTaskMessageMap,
            };
          });
        },

        cancelTask: (taskId, content) => {
          const locatedTaskGroup = get().findTaskMessageGroup(taskId);
          let nextGroup: TaskMessageGroupIds | undefined;

          if (locatedTaskGroup) {
            const { conversationId, logMessage, contentMessage, group } = locatedTaskGroup;
            const hasLogs = Array.isArray(content?.logs);
            const hasAiText = typeof content?.aiText === 'string';
            const hasNonEmptyAiText = hasAiText && (content?.aiText?.length || 0) > 0;

            if (logMessage && getTaskMessageKind(logMessage) === TASK_LOG_KIND) {
              get().updateMessage(conversationId, logMessage.id, {
                status: 'cancelled',
                metadata: {
                  messageKind: TASK_LOG_KIND,
                  ...(hasLogs ? { logs: content?.logs } : {}),
                },
              });
            }

            let contentMessageId: string | undefined = contentMessage?.id;
            if (!contentMessage && hasNonEmptyAiText) {
              contentMessageId =
                get().ensureTaskContentMessage(taskId, {
                  status: 'cancelled',
                  content: content?.aiText || '',
                }) || undefined;
            } else if (contentMessage) {
              get().updateMessage(conversationId, contentMessage.id, {
                status: 'cancelled',
                ...(hasAiText ? { content: content?.aiText || '' } : {}),
                error: undefined,
                metadata: {
                  messageKind: TASK_CONTENT_KIND,
                },
              });
            }

            nextGroup = mergeTaskMessageGroup(group, {
              ...(logMessage ? { logMessageId: logMessage.id } : {}),
              ...(contentMessageId ? { contentMessageId } : {}),
            });
          }

          set((state) => {
            const nextTaskMessageMap = { ...state.taskMessageMap };
            if (nextGroup) {
              nextTaskMessageMap[taskId] = nextGroup;
            } else {
              delete nextTaskMessageMap[taskId];
            }

            return {
              activeTaskIds: state.activeTaskIds.filter((id) => id !== taskId),
              taskMessageMap: nextTaskMessageMap,
            };
          });
        },

        discardStaleTask: (taskId) => {
          set((state) => ({
            conversations: state.conversations.map((conv) => ({
              ...conv,
              messages: conv.messages.filter((msg) => {
                if (msg.taskId !== taskId || msg.status !== 'generating') {
                  return true;
                }

                const kind = getTaskMessageKind(msg);
                if (kind === TASK_DOWNLOAD_KIND) {
                  return true;
                }

                return false;
              }),
            })),
            activeTaskIds: state.activeTaskIds.filter((id) => id !== taskId),
            taskMessageMap: Object.fromEntries(
              Object.entries(state.taskMessageMap).filter(([id]) => id !== taskId)
            ),
          }));
        },

        getCurrentConversation: () => {
          const state = get();
          return (
            state.conversations.find((conv) => conv.id === state.currentConversationId) || null
          );
        },

        hasActiveTasks: () =>
          get().activeTaskIds.length > 0 ||
          get().conversations.some((conversation) =>
            conversation.messages.some((message) => message.status === 'generating')
          ),
        clearError: () => set({ error: null }),
        dismissConcurrentWarning: () => set({ concurrentTaskWarning: false }),
        setSelectedTenderType: (type) => set({ selectedTenderType: type }),

        findConversationByTenderNo: (tenderno) => {
          const state = get();
          return state.conversations.find((conv) => conv.title === tenderno) || null;
        },

        findTaskMessageGroup: (taskId) => {
          const state = get();
          const mappedGroup = state.taskMessageMap[taskId];

          if (mappedGroup) {
            for (const conversation of state.conversations) {
              const logMessage = getMessageById(conversation.messages, mappedGroup.logMessageId);
              const contentMessage = getMessageById(
                conversation.messages,
                mappedGroup.contentMessageId
              );
              const downloadMessage = getMessageById(
                conversation.messages,
                mappedGroup.downloadMessageId
              );

              if (logMessage || contentMessage || downloadMessage) {
                return {
                  conversationId: conversation.id,
                  group: mappedGroup,
                  logMessage,
                  contentMessage,
                  downloadMessage,
                };
              }
            }
          }

          for (const conversation of state.conversations) {
            const taskMessages = conversation.messages.filter((item) => item.taskId === taskId);
            if (taskMessages.length === 0) {
              continue;
            }

            const builtGroup = buildGroupFromMessages(taskMessages);
            const logMessage = getMessageById(conversation.messages, builtGroup.logMessageId);
            const contentMessage = getMessageById(conversation.messages, builtGroup.contentMessageId);
            const downloadMessage = getMessageById(
              conversation.messages,
              builtGroup.downloadMessageId
            );

            if (logMessage || contentMessage || downloadMessage) {
              return {
                conversationId: conversation.id,
                group: builtGroup,
                logMessage,
                contentMessage,
                downloadMessage,
              };
            }

            const legacyMessage = taskMessages.find((message) => message.type === 'ai');
            if (legacyMessage) {
              return {
                conversationId: conversation.id,
                group: { contentMessageId: legacyMessage.id },
                contentMessage: legacyMessage,
              };
            }
          }

          return null;
        },

        findMessageByTaskId: (taskId) => {
          const group = get().findTaskMessageGroup(taskId);
          if (group) {
            const message = group.contentMessage || group.logMessage || group.downloadMessage;
            if (message) {
              return { conversationId: group.conversationId, message };
            }
          }

          const state = get();
          for (const conversation of state.conversations) {
            const message = conversation.messages.find((item) => item.taskId === taskId);
            if (message) {
              return { conversationId: conversation.id, message };
            }
          }
          return null;
        },

        getSortedConversations: () => {
          const state = get();
          return [...state.conversations].sort((a, b) => b.createdAt - a.createdAt);
        },

        getMostRecentConversationByType: (type: TenderType) => {
          const state = get();
          return (
            state.conversations
              .filter((conv) => conv.tenderType === type)
              .sort((a, b) => b.createdAt - a.createdAt)[0] || null
          );
        },
      }),
      {
        name: 'chat-storage',
        storage: createJSONStorage(() => sessionStorage),
        partialize: (state) => ({
          conversations: state.conversations,
          currentConversationId: state.currentConversationId,
          selectedTenderType: state.selectedTenderType,
        }),
      }
    )
  )
);

export default useChatStore;
