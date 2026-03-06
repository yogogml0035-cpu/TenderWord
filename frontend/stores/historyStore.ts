import { create } from 'zustand';
import { createJSONStorage, devtools, persist } from 'zustand/middleware';

export type HistoryStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface HistoryItem {
  /** Unique identifier for the history item */
  id: string;
  /** Task ID */
  taskId: string;
  /** Tender number */
  tenderNo: string;
  /** Tender type */
  tenderType: 'xjcg' | 'gngk';
  /** Tender type display name */
  tenderTypeName: string;
  /** Task status */
  status: HistoryStatus;
  /** Output file path */
  outputFile?: string;
  /** Output file name */
  outputFileName?: string;
  /** Error message if failed */
  errorMessage?: string;
  /** Model used */
  model: string;
  /** Creation time */
  createdAt: string;
  /** Completion time */
  completedAt?: string;
  /** Progress percentage at the time of snapshot */
  progressPercent: number;
}

export interface HistoryStore {
  /** Generation history list */
  history: HistoryItem[];
  /** Add a new history item */
  addToHistory: (item: Omit<HistoryItem, 'id' | 'createdAt'>) => void;
  /** Update an existing history item */
  updateHistoryItem: (taskId: string, updates: Partial<HistoryItem>) => void;
  /** Remove a history item by ID */
  removeFromHistory: (id: string) => void;
  /** Remove a history item by task ID */
  removeFromHistoryByTaskId: (taskId: string) => void;
  /** Clear all history */
  clearHistory: () => void;
  /** Get history by tender number */
  getHistoryByTenderNo: (tenderNo: string) => HistoryItem[];
  /** Get history by status */
  getHistoryByStatus: (status: HistoryStatus) => HistoryItem[];
  /** Get the most recent history items */
  getRecentHistory: (count?: number) => HistoryItem[];
}

const generateId = () => `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

export const useHistoryStore = create<HistoryStore>()(
  devtools(
    persist(
      (set, get) => ({
        history: [],

        addToHistory: (item) => {
          const newItem: HistoryItem = {
            ...item,
            id: generateId(),
            createdAt: new Date().toISOString(),
          };

          set((state) => ({
            history: [newItem, ...state.history].slice(0, 100), // Keep last 100 items
          }));
        },

        updateHistoryItem: (taskId, updates) => {
          set((state) => ({
            history: state.history.map((item) =>
              item.taskId === taskId
                ? {
                    ...item,
                    ...updates,
                    completedAt:
                      updates.status === 'completed' || updates.status === 'failed'
                        ? new Date().toISOString()
                        : item.completedAt,
                  }
                : item
            ),
          }));
        },

        removeFromHistory: (id) => {
          set((state) => ({
            history: state.history.filter((item) => item.id !== id),
          }));
        },

        removeFromHistoryByTaskId: (taskId) => {
          set((state) => ({
            history: state.history.filter((item) => item.taskId !== taskId),
          }));
        },

        clearHistory: () => {
          set({ history: [] });
        },

        getHistoryByTenderNo: (tenderNo) => {
          return get().history.filter((item) => item.tenderNo === tenderNo);
        },

        getHistoryByStatus: (status) => {
          return get().history.filter((item) => item.status === status);
        },

        getRecentHistory: (count = 10) => {
          return get().history.slice(0, count);
        },
      }),
      {
        name: 'tender-history-storage',
        storage: createJSONStorage(() => sessionStorage),
        partialize: (state) => ({
          history: state.history,
        }),
      }
    )
  )
);

export default useHistoryStore;
