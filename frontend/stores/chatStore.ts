import { create } from 'zustand';
import { createJSONStorage, devtools, persist } from 'zustand/middleware';
import type { TenderType } from '@/types';
import type { TaskStatus, TenderData } from '@/types/api';
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

export interface ConversationDraftFile {
  id: string;
  file_path: string;
  file_name: string;
  original_name: string;
  size: number;
  upload_time: string;
  file_type?: string;
}

export interface ConversationFormDraft {
  tender_no?: string;
  tender_data?: TenderData | null;
  model?: 'deepseek' | 'qwen' | 'doubao';
  insertion_config?: {
    before_text: string;
    after_text: string;
  };
  files?: {
    origin_tender?: ConversationDraftFile;
    clean_draft?: ConversationDraftFile;
    tender_params: ConversationDraftFile[];
  };
}

export interface TaskSummarySnapshot {
  task_id: string;
  status: TaskStatus;
  queue_position?: number;
  waiting_count?: number;
  progress_percent?: number;
  progress_text?: string;
  current_node_display?: string;
  updated_at: number;
}

interface TaskScopeState {
  conversations: Conversation[];
  currentConversationId: string | null;
  activeTaskIds: string[];
  taskSummaries: Record<string, TaskSummarySnapshot>;
}

const TERMINAL_TASK_STATUSES = new Set<TaskStatus>(['completed', 'failed', 'cancelled']);

function isTerminalTaskStatus(status?: TaskStatus): boolean {
  if (!status) {
    return false;
  }
  return TERMINAL_TASK_STATUSES.has(status);
}

function normalizeDraftFile(file: ConversationDraftFile | undefined): ConversationDraftFile | undefined {
  if (!file) {
    return undefined;
  }

  return {
    id: file.id,
    file_path: file.file_path,
    file_name: file.file_name,
    original_name: file.original_name,
    size: file.size,
    upload_time: file.upload_time,
    ...(file.file_type ? { file_type: file.file_type } : {}),
  };
}

function mergeConversationDraft(
  base: ConversationFormDraft,
  updates: Partial<ConversationFormDraft>
): ConversationFormDraft {
  const nextDraft: ConversationFormDraft = {
    ...base,
    ...updates,
  };

  if (updates.insertion_config) {
    nextDraft.insertion_config = {
      ...(base.insertion_config || {}),
      ...updates.insertion_config,
    };
  }

  if (updates.files) {
    nextDraft.files = {
      ...(base.files || { tender_params: [] }),
      ...updates.files,
      tender_params: updates.files.tender_params || base.files?.tender_params || [],
    };
  }

  if (nextDraft.files) {
    nextDraft.files = {
      ...(nextDraft.files.origin_tender
        ? { origin_tender: normalizeDraftFile(nextDraft.files.origin_tender) }
        : {}),
      ...(nextDraft.files.clean_draft
        ? { clean_draft: normalizeDraftFile(nextDraft.files.clean_draft) }
        : {}),
      tender_params: (nextDraft.files.tender_params || [])
        .map((file) => normalizeDraftFile(file))
        .filter((file): file is ConversationDraftFile => !!file),
    };
  }

  return nextDraft;
}

function getActiveTaskIdsFromState(state: TaskScopeState): string[] {
  const orderedIds = [...state.activeTaskIds];
  const activeTaskIds = new Set(orderedIds);

  for (const conversation of state.conversations) {
    const taskId = conversation.currentTaskId;
    if (!taskId || activeTaskIds.has(taskId)) {
      continue;
    }

    const summary = state.taskSummaries[taskId];
    if (summary && isTerminalTaskStatus(summary.status)) {
      continue;
    }

    activeTaskIds.add(taskId);
    orderedIds.push(taskId);
  }

  return orderedIds.filter((taskId) => {
    const summary = state.taskSummaries[taskId];
    if (!summary) {
      return true;
    }
    return !isTerminalTaskStatus(summary.status);
  });
}

function getCurrentConversationActiveTaskFromState(state: TaskScopeState): string | null {
  if (!state.currentConversationId) {
    return null;
  }

  const currentConversation = state.conversations.find(
    (conversation) => conversation.id === state.currentConversationId
  );
  if (!currentConversation) {
    return null;
  }

  const taskId = currentConversation.currentTaskId;
  if (!taskId) {
    return null;
  }

  const summary = state.taskSummaries[taskId];
  if (summary && isTerminalTaskStatus(summary.status)) {
    return null;
  }

  return taskId;
}

function getLatestActiveTaskIdFromState(state: TaskScopeState): string | null {
  const activeTaskIds = getActiveTaskIdsFromState(state);
  return activeTaskIds[activeTaskIds.length - 1] || null;
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

function findConversationByTaskIdFromState(
  state: Pick<ChatStore, 'conversations'>,
  taskId: string
): Conversation | null {
  const byBinding = state.conversations.find((conversation) => conversation.currentTaskId === taskId);
  if (byBinding) {
    return byBinding;
  }

  const byMessage = state.conversations.find((conversation) =>
    conversation.messages.some((message) => message.taskId === taskId)
  );
  return byMessage || null;
}

interface ChatStore {
  conversations: Conversation[];
  currentConversationId: string | null;
  activeTaskIds: string[];
  taskMessageMap: Record<string, TaskMessageGroupIds>;
  conversationDrafts: Record<string, ConversationFormDraft>;
  taskSummaries: Record<string, TaskSummarySnapshot>;
  isLoading: boolean;
  error: string | null;
  selectedTenderType: TenderType | null;

  createConversation: (tenderno: string, tenderType: TenderType, title?: string) => string;
  updateConversation: (id: string, updates: Partial<Conversation>) => void;
  deleteConversation: (id: string) => void;
  setCurrentConversation: (id: string | null) => void;
  updateConversationDraft: (conversationId: string, updates: Partial<ConversationFormDraft>) => void;
  clearConversationDraft: (conversationId: string) => void;
  getConversationDraft: (conversationId: string | null) => ConversationFormDraft | null;

  addMessage: (
    conversationId: string,
    message: Omit<Message, 'id' | 'timestamp' | 'conversationId'>
  ) => string;
  updateMessage: (conversationId: string, messageId: string, updates: Partial<Message>) => void;
  deleteMessage: (conversationId: string, messageId: string) => void;

  startTask: (
    conversationId: string,
    taskId: string,
    initialSummary?: Partial<Omit<TaskSummarySnapshot, 'task_id' | 'updated_at'>>
  ) => TaskMessageGroupIds;
  ensureTaskLogMessage: (taskId: string, options?: { status?: Message['status'] }) => string | null;
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
  upsertTaskSummary: (
    taskId: string,
    summary: Omit<TaskSummarySnapshot, 'task_id' | 'updated_at'>
  ) => void;
  removeTaskSummary: (taskId: string) => void;
  getTaskSummary: (taskId: string) => TaskSummarySnapshot | null;

  getCurrentConversation: () => Conversation | null;
  currentConversationActiveTask: () => string | null;
  currentConversationIsBusy: () => boolean;
  latestActiveTaskId: () => string | null;
  otherActiveTaskCount: () => number;
  hasActiveTasks: () => boolean;
  clearError: () => void;
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
        conversationDrafts: {},
        taskSummaries: {},
        isLoading: false,
        error: null,
        selectedTenderType: null,

        createConversation: (tenderno, tenderType, title) => {
          const conversation = createConvUtil(title || tenderno, tenderType);
          set((state) => ({
            conversations: [conversation, ...state.conversations],
            currentConversationId: conversation.id,
            selectedTenderType: tenderType,
            conversationDrafts: {
              ...state.conversationDrafts,
              [conversation.id]: {},
            },
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
            const deletedTaskIds = new Set<string>();

            if (conversationToDelete?.currentTaskId) {
              deletedTaskIds.add(conversationToDelete.currentTaskId);
            }
            for (const message of conversationToDelete?.messages || []) {
              if (typeof message.taskId === 'string') {
                deletedTaskIds.add(message.taskId);
              }
            }
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
              conversationDrafts: Object.fromEntries(
                Object.entries(state.conversationDrafts).filter(
                  ([conversationId]) => conversationId !== id
                )
              ),
              taskSummaries: Object.fromEntries(
                Object.entries(state.taskSummaries).filter(([taskId]) => !deletedTaskIds.has(taskId))
              ),
            };
          });
        },

        setCurrentConversation: (id) => set({ currentConversationId: id }),

        updateConversationDraft: (conversationId, updates) => {
          set((state) => ({
            conversationDrafts: {
              ...state.conversationDrafts,
              [conversationId]: mergeConversationDraft(
                state.conversationDrafts[conversationId] || {},
                updates
              ),
            },
          }));
        },

        clearConversationDraft: (conversationId) =>
          set((state) => ({
            conversationDrafts: Object.fromEntries(
              Object.entries(state.conversationDrafts).filter(([id]) => id !== conversationId)
            ),
          })),

        getConversationDraft: (conversationId) => {
          if (!conversationId) {
            return null;
          }
          return get().conversationDrafts[conversationId] || null;
        },

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

        startTask: (conversationId, taskId, initialSummary) => {
          set((state) => {
            const summarySeed = initialSummary?.status
              ? {
                  [taskId]: {
                    ...(state.taskSummaries[taskId] || {}),
                    task_id: taskId,
                    status: initialSummary.status,
                    ...(typeof initialSummary.queue_position === 'number'
                      ? { queue_position: initialSummary.queue_position }
                      : {}),
                    ...(typeof initialSummary.waiting_count === 'number'
                      ? { waiting_count: initialSummary.waiting_count }
                      : {}),
                    ...(typeof initialSummary.progress_percent === 'number'
                      ? { progress_percent: initialSummary.progress_percent }
                      : {}),
                    ...(typeof initialSummary.progress_text === 'string'
                      ? { progress_text: initialSummary.progress_text }
                      : {}),
                    ...(typeof initialSummary.current_node_display === 'string'
                      ? { current_node_display: initialSummary.current_node_display }
                      : {}),
                    updated_at: Date.now(),
                  },
                }
              : {};

            return {
              conversations: state.conversations.map((conv) =>
                conv.id === conversationId
                  ? { ...conv, currentTaskId: taskId, updatedAt: Date.now() }
                  : conv
              ),
              activeTaskIds: state.activeTaskIds.includes(taskId)
                ? state.activeTaskIds
                : [...state.activeTaskIds, taskId],
              taskSummaries: {
                ...state.taskSummaries,
                ...summarySeed,
              },
            };
          });

          return {};
        },

        ensureTaskLogMessage: (taskId, options) => {
          const existing = get().findTaskMessageGroup(taskId);
          if (existing?.logMessage) {
            if (options?.status && existing.logMessage.status !== options.status) {
              get().updateMessage(existing.conversationId, existing.logMessage.id, {
                status: options.status,
                metadata: {
                  messageKind: TASK_LOG_KIND,
                  logs: existing.logMessage.metadata?.logs || [],
                },
              });
            }
            return existing.logMessage.id;
          }

          const conversation = findConversationByTaskIdFromState(get(), taskId);
          if (!conversation) {
            return null;
          }

          const logMessageId = get().addMessage(conversation.id, {
            type: 'ai',
            content: '',
            status: options?.status || 'generating',
            taskId,
            metadata: {
              messageKind: TASK_LOG_KIND,
              logs: [],
            },
          });

          const currentGroup = get().taskMessageMap[taskId] || {};
          const nextGroup = mergeTaskMessageGroup(currentGroup, { logMessageId });

          set((state) => ({
            taskMessageMap: {
              ...state.taskMessageMap,
              [taskId]: nextGroup,
            },
          }));

          return logMessageId;
        },

        ensureTaskContentMessage: (taskId, options) => {
          let locatedTaskGroup = get().findTaskMessageGroup(taskId);
          if (!locatedTaskGroup) {
            get().ensureTaskLogMessage(taskId, { status: options?.status || 'generating' });
            locatedTaskGroup = get().findTaskMessageGroup(taskId);
          }
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
              conversations: state.conversations.map((conversation) =>
                conversation.currentTaskId === taskId
                  ? { ...conversation, currentTaskId: undefined, updatedAt: Date.now() }
                  : conversation
              ),
              activeTaskIds: state.activeTaskIds.filter((id) => id !== taskId),
              taskMessageMap: nextTaskMessageMap,
              taskSummaries: Object.fromEntries(
                Object.entries(state.taskSummaries).filter(([id]) => id !== taskId)
              ),
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
              conversations: state.conversations.map((conversation) =>
                conversation.currentTaskId === taskId
                  ? { ...conversation, currentTaskId: undefined, updatedAt: Date.now() }
                  : conversation
              ),
              activeTaskIds: state.activeTaskIds.filter((id) => id !== taskId),
              taskMessageMap: nextTaskMessageMap,
              taskSummaries: Object.fromEntries(
                Object.entries(state.taskSummaries).filter(([id]) => id !== taskId)
              ),
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
              conversations: state.conversations.map((conversation) =>
                conversation.currentTaskId === taskId
                  ? { ...conversation, currentTaskId: undefined, updatedAt: Date.now() }
                  : conversation
              ),
              activeTaskIds: state.activeTaskIds.filter((id) => id !== taskId),
              taskMessageMap: nextTaskMessageMap,
              taskSummaries: Object.fromEntries(
                Object.entries(state.taskSummaries).filter(([id]) => id !== taskId)
              ),
            };
          });
        },

        discardStaleTask: (taskId) => {
          set((state) => ({
            conversations: state.conversations.map((conv) => ({
              ...conv,
              currentTaskId: conv.currentTaskId === taskId ? undefined : conv.currentTaskId,
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
            taskSummaries: Object.fromEntries(
              Object.entries(state.taskSummaries).filter(([id]) => id !== taskId)
            ),
          }));
        },

        upsertTaskSummary: (taskId, summary) =>
          set((state) => ({
            taskSummaries: {
              ...state.taskSummaries,
              [taskId]: {
                ...(state.taskSummaries[taskId] || {}),
                ...summary,
                task_id: taskId,
                updated_at: Date.now(),
              },
            },
          })),

        removeTaskSummary: (taskId) =>
          set((state) => ({
            taskSummaries: Object.fromEntries(
              Object.entries(state.taskSummaries).filter(([id]) => id !== taskId)
            ),
          })),

        getTaskSummary: (taskId) => get().taskSummaries[taskId] || null,

        getCurrentConversation: () => {
          const state = get();
          return (
            state.conversations.find((conv) => conv.id === state.currentConversationId) || null
          );
        },

        currentConversationActiveTask: () => {
          const state = get();
          return getCurrentConversationActiveTaskFromState(state);
        },

        currentConversationIsBusy: () => {
          const state = get();
          return getCurrentConversationActiveTaskFromState(state) !== null;
        },

        latestActiveTaskId: () => {
          const state = get();
          return getLatestActiveTaskIdFromState(state);
        },

        otherActiveTaskCount: () => {
          const state = get();
          const latestTaskId = getLatestActiveTaskIdFromState(state);
          if (!latestTaskId) {
            return 0;
          }

          return getActiveTaskIdsFromState(state).filter((taskId) => taskId !== latestTaskId).length;
        },

        hasActiveTasks: () => getActiveTaskIdsFromState(get()).length > 0,
        clearError: () => set({ error: null }),
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
          conversationDrafts: state.conversationDrafts,
          taskSummaries: state.taskSummaries,
        }),
      }
    )
  )
);

export default useChatStore;
