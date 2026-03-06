import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

export interface TaskSessionState {
  taskId: string;
  lastEventId?: string;
}

interface ChatTaskSessionStore {
  sessions: Record<string, TaskSessionState>;
  upsertSession: (taskId: string, next?: Partial<TaskSessionState>) => void;
  removeSession: (taskId: string) => void;
  clearSessions: () => void;
}

export const useChatTaskSessionStore = create<ChatTaskSessionStore>()(
  persist(
    (set) => ({
      sessions: {},

      upsertSession: (taskId, next) =>
        set((state) => ({
          sessions: {
            ...state.sessions,
            [taskId]: {
              ...(state.sessions[taskId] || {}),
              ...next,
              taskId,
            },
          },
        })),

      removeSession: (taskId) =>
        set((state) => ({
          sessions: Object.fromEntries(
            Object.entries(state.sessions).filter(([id]) => id !== taskId)
          ),
        })),

      clearSessions: () => set({ sessions: {} }),
    }),
    {
      name: 'chat-task-session-storage',
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        sessions: state.sessions,
      }),
    }
  )
);

export default useChatTaskSessionStore;
