import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import type { TenderType } from '@/types';
import type { Conversation, Message } from '@/types/chat';
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
  completeTask: (taskId: string, outputFile?: string, fileName?: string) => void;
  failTask: (taskId: string, error: string) => void;
  cancelTask: (taskId: string) => void;

  getCurrentConversation: () => Conversation | null;
  hasActiveTasks: () => boolean;
  clearError: () => void;
  dismissConcurrentWarning: () => void;
  setSelectedTenderType: (type: TenderType | null) => void;
  findConversationByTenderNo: (tenderno: string) => Conversation | null;
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
            const newConversations = state.conversations.filter((conv) => conv.id !== id);
            return {
              conversations: newConversations,
              currentConversationId:
                state.currentConversationId === id
                  ? newConversations[0]?.id || null
                  : state.currentConversationId,
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
          if (state.activeTaskIds.length > 0) {
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

        completeTask: (taskId, outputFile?, fileName?) => {
          const state = get();
          const messageId = state.taskMessageMap[taskId];
          const conversationId = state.conversations.find((conv) =>
            conv.messages.some((msg) => msg.id === messageId)
          )?.id;

          if (conversationId && messageId) {
            get().updateMessage(conversationId, messageId, {
              status: 'completed',
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

        failTask: (taskId, error) => {
          const state = get();
          const messageId = state.taskMessageMap[taskId];
          const conversationId = state.conversations.find((conv) =>
            conv.messages.some((msg) => msg.id === messageId)
          )?.id;

          if (conversationId && messageId) {
            get().updateMessage(conversationId, messageId, { status: 'error', error });
          }

          set((state) => ({
            activeTaskIds: state.activeTaskIds.filter((id) => id !== taskId),
            taskMessageMap: Object.fromEntries(
              Object.entries(state.taskMessageMap).filter(([id]) => id !== taskId)
            ),
          }));
        },

        cancelTask: (taskId) => {
          const state = get();
          const messageId = state.taskMessageMap[taskId];
          const conversationId = state.conversations.find((conv) =>
            conv.messages.some((msg) => msg.id === messageId)
          )?.id;

          if (conversationId && messageId) {
            get().updateMessage(conversationId, messageId, { status: 'cancelled' });
          }

          set((state) => ({
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

        hasActiveTasks: () => get().activeTaskIds.length > 0,
        clearError: () => set({ error: null }),
        dismissConcurrentWarning: () => set({ concurrentTaskWarning: false }),
        setSelectedTenderType: (type) => set({ selectedTenderType: type }),

        findConversationByTenderNo: (tenderno) => {
          const state = get();
          return state.conversations.find((conv) => conv.title === tenderno) || null;
        },
      }),
      {
        name: 'chat-storage',
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
