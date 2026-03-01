import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import type { Task, GenerationHistory, TenderType } from '@/types';

interface AppState {
  // Sidebar state
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;

  // Current task
  currentTask: Task | null;
  setCurrentTask: (task: Task | null) => void;
  updateTaskProgress: (progress: number, message?: string) => void;

  // Generation history
  history: GenerationHistory[];
  addToHistory: (item: GenerationHistory) => void;
  removeFromHistory: (id: string) => void;
  clearHistory: () => void;

  // Active tender type
  activeTenderType: TenderType | null;
  setActiveTenderType: (type: TenderType | null) => void;

  // UI State
  isGenerating: boolean;
  setIsGenerating: (value: boolean) => void;
}

export const useAppStore = create<AppState>()(
  devtools(
    persist(
      (set) => ({
        // Sidebar
        sidebarOpen: true,
        toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
        setSidebarOpen: (open) => set({ sidebarOpen: open }),

        // Current task
        currentTask: null,
        setCurrentTask: (task) => set({ currentTask: task }),
        updateTaskProgress: (progress, message) =>
          set((state) => ({
            currentTask: state.currentTask
              ? {
                  ...state.currentTask,
                  progress,
                  message: message ?? state.currentTask.message,
                  updatedAt: new Date(),
                }
              : null,
          })),

        // History
        history: [],
        addToHistory: (item) =>
          set((state) => ({
            history: [item, ...state.history].slice(0, 50), // Keep last 50 items
          })),
        removeFromHistory: (id) =>
          set((state) => ({
            history: state.history.filter((item) => item.id !== id),
          })),
        clearHistory: () => set({ history: [] }),

        // Tender type
        activeTenderType: null,
        setActiveTenderType: (type) => set({ activeTenderType: type }),

        // UI State
        isGenerating: false,
        setIsGenerating: (value) => set({ isGenerating: value }),
      }),
      {
        name: 'tender-app-storage',
        partialize: (state) => ({
          sidebarOpen: state.sidebarOpen,
          history: state.history,
        }),
      }
    )
  )
);
