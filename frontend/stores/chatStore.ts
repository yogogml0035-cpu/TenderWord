import { create } from 'zustand';
import { createJSONStorage, devtools, persist } from 'zustand/middleware';
import type { TenderType } from '@/types';
import type { Conversation, Message, DualColumnContent } from '@/types/chat';
import { createConversation as createConvUtil, generateMessageId } from '@/lib/chat-utils';

interface ChatStore {
  conversations: Conversation[];
  currentConversationId: string | null;
  activeTaskIds: string[];
  taskMessageMap: Record<string, string>;
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

  startTask: (conversationId: string, taskId: string) => string;
  completeTask: (
    taskId: string,
    outputFile?: string,
    fileName?: string,
    content?: DualColumnContent
  ) => void;
  failTask: (taskId: string, error: string, content?: DualColumnContent) => void;
  cancelTask: (taskId: string, content?: DualColumnContent) => void;
  discardStaleTask: (taskId: string) => void;

  getCurrentConversation: () => Conversation | null;
  hasActiveTasks: () => boolean;
  clearError: () => void;
  dismissConcurrentWarning: () => void;
  setSelectedTenderType: (type: TenderType | null) => void;
  findConversationByTenderNo: (tenderno: string) => Conversation | null;
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

          const messageId = get().addMessage(conversationId, {
            type: 'ai',
            content: {
              logs: [],
              aiContent: { text: '', timestamp: Date.now(), isComplete: false },
            },
            status: 'generating',
            taskId,
          });

          set((state) => ({
            activeTaskIds: [...state.activeTaskIds, taskId],
            taskMessageMap: { ...state.taskMessageMap, [taskId]: messageId },
          }));

          return messageId;
        },

        completeTask: (taskId, outputFile?, fileName?, content?) => {
          const locatedMessage = get().findMessageByTaskId(taskId);

          if (locatedMessage) {
            get().updateMessage(locatedMessage.conversationId, locatedMessage.message.id, {
              status: 'completed',
              ...(content ? { content } : {}),
              metadata: { outputFile, fileName },
            });
          }

          set((state) => ({
            activeTaskIds: state.activeTaskIds.filter((id) => id !== taskId),
            taskMessageMap: Object.fromEntries(
              Object.entries(state.taskMessageMap).filter(([id]) => id !== taskId)
            ),
          }));
        },

        failTask: (taskId, error, content?) => {
          const locatedMessage = get().findMessageByTaskId(taskId);

          if (locatedMessage) {
            get().updateMessage(locatedMessage.conversationId, locatedMessage.message.id, {
              status: 'error',
              error,
              ...(content ? { content } : {}),
            });
          }

          set((state) => ({
            activeTaskIds: state.activeTaskIds.filter((id) => id !== taskId),
            taskMessageMap: Object.fromEntries(
              Object.entries(state.taskMessageMap).filter(([id]) => id !== taskId)
            ),
          }));
        },

        cancelTask: (taskId, content?) => {
          const locatedMessage = get().findMessageByTaskId(taskId);

          if (locatedMessage) {
            get().updateMessage(locatedMessage.conversationId, locatedMessage.message.id, {
              status: 'cancelled',
              ...(content ? { content } : {}),
            });
          }

          set((state) => ({
            activeTaskIds: state.activeTaskIds.filter((id) => id !== taskId),
            taskMessageMap: Object.fromEntries(
              Object.entries(state.taskMessageMap).filter(([id]) => id !== taskId)
            ),
          }));
        },

        discardStaleTask: (taskId) => {
          set((state) => ({
            conversations: state.conversations.map((conv) => ({
              ...conv,
              messages: conv.messages.filter(
                (msg) => !(msg.taskId === taskId && msg.status === 'generating')
              ),
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

        findMessageByTaskId: (taskId) => {
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
