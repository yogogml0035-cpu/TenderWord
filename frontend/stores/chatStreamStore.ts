import { create } from 'zustand';
import type { DualColumnContent, LogEntry } from '@/types/chat';
import { createEmptyDualColumnContent } from '@/lib/chat-utils';

export interface TaskStreamState {
  content: DualColumnContent;
  lastEventId?: string;
  progressPercent?: number;
  progressText?: string;
  currentNode?: string;
  currentNodeDisplay?: string;
}

interface ChatStreamStore {
  streams: Record<string, TaskStreamState>;
  ensureStream: (taskId: string) => void;
  replaceStream: (taskId: string, next?: Partial<TaskStreamState>) => void;
  appendLog: (taskId: string, log: LogEntry) => void;
  setAIContent: (taskId: string, text: string, isComplete: boolean) => void;
  setProgress: (
    taskId: string,
    progress: Pick<
      TaskStreamState,
      'progressPercent' | 'progressText' | 'currentNode' | 'currentNodeDisplay'
    >
  ) => void;
  setLastEventId: (taskId: string, lastEventId?: string) => void;
  clearStream: (taskId: string) => void;
}

function createStreamState(overrides?: Partial<TaskStreamState>): TaskStreamState {
  return {
    content: createEmptyDualColumnContent(),
    ...overrides,
  };
}

export const useChatStreamStore = create<ChatStreamStore>()((set) => ({
  streams: {},

  ensureStream: (taskId) =>
    set((state) => {
      if (state.streams[taskId]) {
        return state;
      }
      return {
        streams: {
          ...state.streams,
          [taskId]: createStreamState(),
        },
      };
    }),

  replaceStream: (taskId, next) =>
    set((state) => ({
      streams: {
        ...state.streams,
        [taskId]: createStreamState(next),
      },
    })),

  appendLog: (taskId, log) =>
    set((state) => {
      const current = state.streams[taskId] ?? createStreamState();
      return {
        streams: {
          ...state.streams,
          [taskId]: {
            ...current,
            content: {
              ...current.content,
              logs: [...current.content.logs, log],
            },
          },
        },
      };
    }),

  setAIContent: (taskId, text, isComplete) =>
    set((state) => {
      const current = state.streams[taskId] ?? createStreamState();
      return {
        streams: {
          ...state.streams,
          [taskId]: {
            ...current,
            content: {
              ...current.content,
              aiContent: {
                text,
                timestamp: Date.now(),
                isComplete,
              },
            },
          },
        },
      };
    }),

  setProgress: (taskId, progress) =>
    set((state) => {
      const current = state.streams[taskId] ?? createStreamState();
      return {
        streams: {
          ...state.streams,
          [taskId]: {
            ...current,
            ...progress,
          },
        },
      };
    }),

  setLastEventId: (taskId, lastEventId) =>
    set((state) => {
      const current = state.streams[taskId] ?? createStreamState();
      return {
        streams: {
          ...state.streams,
          [taskId]: {
            ...current,
            lastEventId,
          },
        },
      };
    }),

  clearStream: (taskId) =>
    set((state) => ({
      streams: Object.fromEntries(Object.entries(state.streams).filter(([id]) => id !== taskId)),
    })),
}));

export default useChatStreamStore;
