import { create } from 'zustand';
import type { LogEntry } from '@/types/chat';
import type { SSECommentAgentStep, SSEContentAgentStep } from '@/types/api';

export interface TaskStreamState {
  logs: LogEntry[];
  aiText: string;
  aiComplete: boolean;
  agentSteps?: Record<
    string,
    {
      content: string;
      contentAgent?: SSEContentAgentStep;
      commentAgent?: SSECommentAgentStep;
      isComplete: boolean;
    }
  >;
  lastCompleteAiText?: string;
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
  setAgentStep: (
    taskId: string,
    stepKey: string,
    snapshot: {
      content: string;
      contentAgent?: SSEContentAgentStep;
      commentAgent?: SSECommentAgentStep;
      isComplete: boolean;
    }
  ) => void;
  setLastEventId: (taskId: string, lastEventId?: string) => void;
  clearStream: (taskId: string) => void;
}

function createStreamState(overrides?: Partial<TaskStreamState>): TaskStreamState {
  return {
    logs: [],
    aiText: '',
    aiComplete: false,
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
            logs: [...current.logs, log],
          },
        },
      };
    }),

  setAIContent: (taskId, text, isComplete) =>
    set((state) => {
      const current = state.streams[taskId] ?? createStreamState();
      const nextStream: TaskStreamState = {
        ...current,
        aiText: text,
        aiComplete: isComplete,
      };
      if (isComplete) {
        nextStream.lastCompleteAiText = text;
      }
      return {
        streams: {
          ...state.streams,
          [taskId]: nextStream,
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

  setAgentStep: (taskId, stepKey, snapshot) =>
    set((state) => {
      const current = state.streams[taskId] ?? createStreamState();
      return {
        streams: {
          ...state.streams,
          [taskId]: {
            ...current,
            agentSteps: {
              ...(current.agentSteps || {}),
              [stepKey]: snapshot,
            },
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
