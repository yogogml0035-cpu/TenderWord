'use client';

import { useEffect } from 'react';
import { getTaskStatus } from '@/lib/api';
import { useChatStore } from '@/stores/chatStore';

const DEFAULT_POLL_INTERVAL_MS = 5000;

export function useLatestActiveTaskSummary(pollIntervalMs: number = DEFAULT_POLL_INTERVAL_MS) {
  const latestActiveTaskId = useChatStore((state) => state.latestActiveTaskId());
  const otherActiveTaskCount = useChatStore((state) => state.otherActiveTaskCount());
  const taskSummaries = useChatStore((state) => state.taskSummaries);
  const upsertTaskSummary = useChatStore((state) => state.upsertTaskSummary);

  useEffect(() => {
    if (!latestActiveTaskId) {
      return;
    }

    let disposed = false;

    const syncLatestTaskSummary = async () => {
      try {
        const task = await getTaskStatus(latestActiveTaskId);
        if (disposed) {
          return;
        }

        upsertTaskSummary(latestActiveTaskId, {
          status: task.status,
          queue_position: task.queue_position,
          waiting_count: task.waiting_count,
          progress_percent: task.progress.progress_percent,
          progress_text: task.progress.progress_text || '',
          current_node_display:
            task.progress.current_node_display || task.progress.current_node || '',
        });
      } catch {
        // 摘要轮询失败不影响会话内主流程
      }
    };

    void syncLatestTaskSummary();
    const timer = window.setInterval(() => {
      void syncLatestTaskSummary();
    }, pollIntervalMs);

    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [latestActiveTaskId, pollIntervalMs, upsertTaskSummary]);

  return {
    latestActiveTaskId,
    otherActiveTaskCount,
    latestTaskSummary: latestActiveTaskId ? taskSummaries[latestActiveTaskId] || null : null,
  };
}

export default useLatestActiveTaskSummary;
