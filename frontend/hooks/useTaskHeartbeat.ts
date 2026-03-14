'use client';

import { useEffect } from 'react';
import { sendTaskHeartbeat } from '@/lib/api';
import type { TaskStatus } from '@/types/api';

const HEARTBEAT_INTERVAL_MS = 5000;
const TASK_ID_SEPARATOR = '\u0001';
const TERMINAL_TASK_STATUSES = new Set<TaskStatus>(['completed', 'failed', 'cancelled']);

interface UseTaskHeartbeatOptions {
  onTerminalState?: (taskId: string, status: TaskStatus) => void;
  onMissingTask?: (taskId: string) => void;
}

export function useTaskHeartbeat(
  taskIds: string | string[] | null,
  options: UseTaskHeartbeatOptions = {}
) {
  const { onTerminalState, onMissingTask } = options;
  const normalizedTaskIds = Array.isArray(taskIds)
    ? [...new Set(taskIds.filter((taskId): taskId is string => typeof taskId === 'string' && taskId.length > 0))]
    : typeof taskIds === 'string' && taskIds.length > 0
      ? [taskIds]
      : [];
  const taskIdsKey = normalizedTaskIds.join(TASK_ID_SEPARATOR);

  useEffect(() => {
    const activeTaskIds = taskIdsKey ? taskIdsKey.split(TASK_ID_SEPARATOR) : [];
    if (activeTaskIds.length === 0) {
      return;
    }

    let isDisposed = false;

    const beat = async () => {
      const results = await Promise.allSettled(
        activeTaskIds.map(async (taskId) => {
          try {
            return {
              taskId,
              heartbeat: await sendTaskHeartbeat(taskId),
            };
          } catch (error) {
            throw {
              taskId,
              code:
                typeof error === 'object' && error !== null
                  ? (error as { code?: string }).code
                  : undefined,
              status:
                typeof error === 'object' && error !== null
                  ? (error as { status?: number }).status
                  : undefined,
            };
          }
        })
      );

      if (isDisposed) {
        return;
      }

      for (const result of results) {
        if (result.status !== 'fulfilled') {
          const reason = result.reason as { taskId?: string; code?: string; status?: number } | undefined;
          const missingTaskId = typeof reason?.taskId === 'string' ? reason.taskId : null;
          const isTaskMissing =
            reason?.code === 'TASK_NOT_FOUND' || reason?.status === 404;
          if (missingTaskId && isTaskMissing) {
            onMissingTask?.(missingTaskId);
          }
          continue;
        }

        const { taskId, heartbeat } = result.value;
        const status = heartbeat.status;
        if (status && TERMINAL_TASK_STATUSES.has(status)) {
          onTerminalState?.(taskId, status);
        }
      }
    };

    void beat();
    const intervalId = window.setInterval(() => {
      void beat();
    }, HEARTBEAT_INTERVAL_MS);

    const handleFocus = () => {
      void beat();
    };
    const handlePageShow = () => {
      void beat();
    };
    const handleOnline = () => {
      void beat();
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        void beat();
      }
    };

    window.addEventListener('focus', handleFocus);
    window.addEventListener('pageshow', handlePageShow);
    window.addEventListener('online', handleOnline);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      isDisposed = true;
      window.clearInterval(intervalId);
      window.removeEventListener('focus', handleFocus);
      window.removeEventListener('pageshow', handlePageShow);
      window.removeEventListener('online', handleOnline);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [onMissingTask, onTerminalState, taskIdsKey]);
}

export default useTaskHeartbeat;
