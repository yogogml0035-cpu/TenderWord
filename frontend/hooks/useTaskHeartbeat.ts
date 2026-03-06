'use client';

import { useEffect } from 'react';
import { sendTaskHeartbeat } from '@/lib/api';

const HEARTBEAT_INTERVAL_MS = 5000;

export function useTaskHeartbeat(taskId: string | null) {
  useEffect(() => {
    if (!taskId) {
      return;
    }

    let isDisposed = false;

    const beat = async () => {
      try {
        await sendTaskHeartbeat(taskId);
      } catch {
        if (isDisposed) {
          return;
        }
      }
    };

    void beat();
    const intervalId = window.setInterval(() => {
      void beat();
    }, HEARTBEAT_INTERVAL_MS);

    return () => {
      isDisposed = true;
      window.clearInterval(intervalId);
    };
  }, [taskId]);
}

export default useTaskHeartbeat;
