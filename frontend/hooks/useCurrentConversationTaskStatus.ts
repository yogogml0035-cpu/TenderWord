'use client';

import { useEffect, useMemo, useState } from 'react';
import { getTaskList, getTaskStatus } from '@/lib/api';
import type { TaskProgress as ApiTaskProgress, TaskStatus } from '@/types/api';
import { useChatStore } from '@/stores/chatStore';

const DEFAULT_POLL_INTERVAL_MS = 5000;
const STARTING_TASK_POLL_INTERVAL_MS = 400;

export interface RunningTaskProgressSnapshot {
  completed_count: number;
  total_nodes: number;
  progress_percent: number;
  progress_text: string;
}

function getTaskWaitingCount(taskSummary?: {
  waiting_count?: number;
  queue_position?: number;
} | null): number | undefined {
  if (typeof taskSummary?.waiting_count === 'number') {
    return taskSummary.waiting_count;
  }
  if (typeof taskSummary?.queue_position === 'number') {
    return taskSummary.queue_position;
  }
  return undefined;
}

function isTaskNotFoundError(error: unknown): boolean {
  if (!error || typeof error !== 'object') {
    return false;
  }

  const maybeError = error as { code?: unknown; status?: unknown };
  return maybeError.code === 'TASK_NOT_FOUND' || maybeError.status === 404;
}

function getProgressText(progress?: Partial<ApiTaskProgress> | null): string {
  if (typeof progress?.progress_text === 'string' && progress.progress_text.trim()) {
    return progress.progress_text;
  }

  if (
    typeof progress?.completed_count === 'number' &&
    typeof progress?.total_nodes === 'number'
  ) {
    return `${progress.completed_count}/${Math.max(1, progress.total_nodes)}`;
  }

  return '';
}

function normalizeRunningTaskProgress(
  progress?: Partial<ApiTaskProgress> | null
): RunningTaskProgressSnapshot | null {
  if (
    typeof progress?.completed_count !== 'number' ||
    typeof progress?.total_nodes !== 'number'
  ) {
    return null;
  }

  const totalNodes = Math.max(1, progress.total_nodes);
  const rawPercent =
    typeof progress.progress_percent === 'number'
      ? progress.progress_percent
      : (progress.completed_count / totalNodes) * 100;

  return {
    completed_count: progress.completed_count,
    total_nodes: totalNodes,
    progress_percent: Math.max(0, Math.min(100, rawPercent)),
    progress_text: getProgressText({
      ...progress,
      total_nodes: totalNodes,
    }),
  };
}

function hasCurrentRunningProgressField(task: {
  current_running_progress?: Partial<ApiTaskProgress> | null;
}): boolean {
  return Object.prototype.hasOwnProperty.call(task, 'current_running_progress');
}

export function useCurrentConversationTaskStatus(
  pollIntervalMs: number = DEFAULT_POLL_INTERVAL_MS
) {
  const getCurrentConversation = useChatStore((state) => state.getCurrentConversation);
  const taskSummaries = useChatStore((state) => state.taskSummaries);
  const upsertTaskSummary = useChatStore((state) => state.upsertTaskSummary);
  const discardStaleTask = useChatStore((state) => state.discardStaleTask);
  const [runningTaskProgressByTaskId, setRunningTaskProgressByTaskId] = useState<{
    taskId: string;
    progress: RunningTaskProgressSnapshot | null;
  } | null>(null);

  const conversation = getCurrentConversation();
  const currentTaskId = conversation?.currentTaskId || null;
  const currentTaskSummary = currentTaskId ? taskSummaries[currentTaskId] || null : null;

  useEffect(() => {
    if (!currentTaskId) {
      return;
    }

    let disposed = false;
    let timer: number | null = null;

    const syncCurrentTask = async (): Promise<number> => {
      let nextPollIntervalMs = pollIntervalMs;

      try {
        const task = await getTaskStatus(currentTaskId);
        if (disposed) {
          return nextPollIntervalMs;
        }

        const normalizedTaskProgress = normalizeRunningTaskProgress(task.progress);

        upsertTaskSummary(currentTaskId, {
          status: task.status,
          queue_position: task.queue_position,
          waiting_count: task.waiting_count,
          ...(typeof normalizedTaskProgress?.progress_percent === 'number'
            ? { progress_percent: normalizedTaskProgress.progress_percent }
            : {}),
          progress_text: normalizedTaskProgress?.progress_text || getProgressText(task.progress),
          current_node_display:
            task.progress.current_node_display || task.progress.current_node || '',
        });

        if (task.status === 'running') {
          setRunningTaskProgressByTaskId({
            taskId: currentTaskId,
            progress: normalizedTaskProgress,
          });
          return nextPollIntervalMs;
        }

        if (task.status !== 'queued') {
          setRunningTaskProgressByTaskId({
            taskId: currentTaskId,
            progress: null,
          });
          return nextPollIntervalMs;
        }

        if (typeof task.waiting_count === 'number' && task.waiting_count <= 0) {
          nextPollIntervalMs = Math.min(STARTING_TASK_POLL_INTERVAL_MS, pollIntervalMs);
        }

        const currentRunningProgress = normalizeRunningTaskProgress(task.current_running_progress);
        if (hasCurrentRunningProgressField(task)) {
          setRunningTaskProgressByTaskId({
            taskId: currentTaskId,
            progress: currentRunningProgress,
          });
          return nextPollIntervalMs;
        }

        try {
          const runningTasks = await getTaskList({ status: 'running' });
          if (disposed) {
            return nextPollIntervalMs;
          }

          const headRunningTask = runningTasks.tasks[0];
          const progress = normalizeRunningTaskProgress(headRunningTask?.progress);
          if (progress) {
            setRunningTaskProgressByTaskId({
              taskId: currentTaskId,
              progress,
            });
          } else {
            setRunningTaskProgressByTaskId({
              taskId: currentTaskId,
              progress: null,
            });
          }
        } catch {
          if (!disposed) {
            setRunningTaskProgressByTaskId({
              taskId: currentTaskId,
              progress: null,
            });
          }
        }
      } catch (error) {
        if (disposed) {
          return nextPollIntervalMs;
        }
        if (isTaskNotFoundError(error)) {
          discardStaleTask(currentTaskId);
        }
      }

      return nextPollIntervalMs;
    };

    const scheduleSync = async () => {
      const nextPollIntervalMs = await syncCurrentTask();
      if (disposed) {
        return;
      }
      timer = window.setTimeout(() => {
        void scheduleSync();
      }, nextPollIntervalMs);
    };

    void scheduleSync();

    return () => {
      disposed = true;
      if (timer !== null) {
        window.clearTimeout(timer);
      }
    };
  }, [currentTaskId, discardStaleTask, pollIntervalMs, upsertTaskSummary]);

  const currentTaskStatus = (currentTaskSummary?.status || null) as TaskStatus | null;
  const waitingCount = useMemo(() => getTaskWaitingCount(currentTaskSummary), [currentTaskSummary]);

  return {
    currentTaskId,
    currentTaskSummary,
    currentTaskStatus,
    waitingCount,
    isCurrentTaskQueued: currentTaskStatus === 'queued',
    isCurrentTaskRunning: currentTaskStatus === 'running',
    runningTaskProgress:
      runningTaskProgressByTaskId?.taskId === currentTaskId
        ? runningTaskProgressByTaskId.progress
        : null,
  };
}

export default useCurrentConversationTaskStatus;
