'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { getTaskStatus } from '@/lib/api';
import { generateLogEntryId } from '@/lib/chat-utils';
import type {
  SSEDoneEvent,
  SSEErrorEvent,
  SSELLMEvent,
  SSEProgressEvent,
  TaskData,
} from '@/types/api';
import type { DualColumnContent, LogEntry } from '@/types/chat';
import { useChatStore } from '@/stores/chatStore';
import { useChatStreamStore } from '@/stores/chatStreamStore';
import { useChatTaskSessionStore } from '@/stores/chatTaskSessionStore';
import { useSSE } from './useSSE';

interface UseChatSSEOptions {
  taskId: string | null;
  conversationId: string | null;
  messageId: string | null;
  onComplete?: () => void;
  onError?: (error: string) => void;
}

/**
 * Hook that maps SSE events to message updates in chatStore.
 *
 * - Log events → left column (logs array)
 * - LLM events → right column (aiContent.text)
 * - Progress events → status updates (console logged)
 * - Done/error events → completion handling
 *
 * @example
 * ```tsx
 * function ChatMessage({ taskId, conversationId, messageId }) {
 *   const { isConnected, error } = useChatSSE({
 *     taskId,
 *     conversationId,
 *     messageId,
 *     onComplete: () => console.log('Task completed'),
 *     onError: (err) => console.error('Task failed:', err),
 *   });
 *
 *   return <div>{isConnected ? 'Connected' : 'Disconnected'}</div>;
 * }
 * ```
 */
export function useChatSSE({
  taskId,
  conversationId,
  messageId,
  onComplete,
  onError,
}: UseChatSSEOptions) {
  void conversationId;
  void messageId;
  const completeTask = useChatStore((state) => state.completeTask);
  const failTask = useChatStore((state) => state.failTask);
  const cancelTask = useChatStore((state) => state.cancelTask);
  const discardStaleTask = useChatStore((state) => state.discardStaleTask);
  const [connectionTaskId, setConnectionTaskId] = useState<string | null>(null);
  const [connectionLastEventId, setConnectionLastEventId] = useState<string | null>(null);
  const handledTerminalTasksRef = useRef<Set<string>>(new Set());
  const onCompleteRef = useRef<typeof onComplete>(onComplete);
  const onErrorRef = useRef<typeof onError>(onError);

  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  const clearTaskRuntime = useCallback(
    (targetTaskId: string) => {
      useChatStreamStore.getState().clearStream(targetTaskId);
      useChatTaskSessionStore.getState().removeSession(targetTaskId);
    },
    []
  );

  const discardStaleTaskRuntime = useCallback(
    (targetTaskId: string) => {
      discardStaleTask(targetTaskId);
      clearTaskRuntime(targetTaskId);
      setConnectionTaskId(null);
      setConnectionLastEventId(null);
    },
    [clearTaskRuntime, discardStaleTask]
  );

  const getCurrentContent = useCallback(
    (targetTaskId: string, forceComplete: boolean = false): DualColumnContent | undefined => {
      const stream = useChatStreamStore.getState().streams[targetTaskId];
      if (!stream) {
        return undefined;
      }

      return {
        ...stream.content,
        aiContent: {
          ...stream.content.aiContent,
          isComplete: forceComplete || stream.content.aiContent.isComplete,
          timestamp: Date.now(),
        },
      };
    },
    []
  );

  const extractOutputInfo = useCallback((task: Pick<TaskData, 'result'>) => {
    const rawResult = task.result;
    if (!rawResult || typeof rawResult === 'string') {
      const outputFile =
        typeof rawResult === 'string' && rawResult !== 'success' ? rawResult : undefined;
      const fileName = typeof outputFile === 'string' ? outputFile.split(/[\\/]/).pop() : undefined;
      return { outputFile, fileName };
    }

    const outputFile =
      typeof rawResult.output_file === 'string' ? rawResult.output_file : undefined;
    const fileName =
      typeof rawResult.file_name === 'string'
        ? rawResult.file_name
        : typeof outputFile === 'string'
          ? outputFile.split(/[\\/]/).pop()
          : undefined;

    return { outputFile, fileName };
  }, []);

  const finalizeFromTaskStatus = useCallback(
    (targetTaskId: string, task: TaskData) => {
      if (handledTerminalTasksRef.current.has(targetTaskId)) {
        return;
      }
      handledTerminalTasksRef.current.add(targetTaskId);

      const finalContent = getCurrentContent(targetTaskId, task.status === 'completed');

      if (task.status === 'completed') {
        const { outputFile, fileName } = extractOutputInfo(task);
        completeTask(targetTaskId, outputFile, fileName, finalContent);
        clearTaskRuntime(targetTaskId);
        onCompleteRef.current?.();
        return;
      }

      if (task.status === 'cancelled') {
        cancelTask(targetTaskId, finalContent);
        clearTaskRuntime(targetTaskId);
        onCompleteRef.current?.();
        return;
      }

      if (task.status === 'failed') {
        const errorMessage = task.error || '生成失败';
        failTask(targetTaskId, errorMessage, finalContent);
        clearTaskRuntime(targetTaskId);
        onErrorRef.current?.(errorMessage);
      }
    },
    [
      cancelTask,
      clearTaskRuntime,
      completeTask,
      extractOutputInfo,
      failTask,
      getCurrentContent,
    ]
  );

  const rememberEventId = useCallback((targetTaskId: string, eventId?: string) => {
    if (!eventId) {
      return;
    }
    useChatStreamStore.getState().setLastEventId(targetTaskId, eventId);
    useChatTaskSessionStore.getState().upsertSession(targetTaskId, { lastEventId: eventId });
  }, []);

  const normalizeLogLevel = useCallback((level: unknown): LogEntry['level'] => {
    const normalized = String(level || 'info').toLowerCase();
    if (normalized === 'warning') {
      return 'warn';
    }
    if (normalized === 'warn' || normalized === 'error' || normalized === 'debug') {
      return normalized;
    }
    return 'info';
  }, []);

  const parseTimestamp = useCallback((value: unknown): number => {
    if (typeof value !== 'string') {
      return Date.now();
    }
    const parsed = Date.parse(value);
    return Number.isNaN(parsed) ? Date.now() : parsed;
  }, []);

  const handleMessage = useCallback(
    (sseMessage: { event: string; data: unknown; id?: string }) => {
      if (!taskId) {
        return;
      }

      const { event, data, id } = sseMessage;
      rememberEventId(taskId, id);

      switch (event) {
        case 'log':
          if (data && typeof data === 'object') {
            const logData = data as Record<string, unknown>;
            const logMessage = (logData.message as string) || '';
            if (logMessage === 'SSE连接已建立') {
              break;
            }
            const logEntry: LogEntry = {
              id: generateLogEntryId(),
              timestamp: parseTimestamp(logData.timestamp),
              level: normalizeLogLevel(logData.level),
              message: logMessage,
              node: logData.node as string | undefined,
            };
            useChatStreamStore.getState().appendLog(taskId, logEntry);
          }
          break;

        case 'llm':
          if (data && typeof data === 'object') {
            const llmData = data as SSELLMEvent;
            const nextText = llmData.content || '';
            const isComplete = llmData.is_complete || false;
            const contentMode = llmData.content_mode || 'snapshot';

            if (contentMode === 'chunk') {
              const currentText =
                useChatStreamStore.getState().streams[taskId]?.content.aiContent.text || '';
              useChatStreamStore
                .getState()
                .setAIContent(taskId, currentText + nextText, isComplete);
            } else {
              useChatStreamStore.getState().setAIContent(taskId, nextText, isComplete);
            }
          }
          break;

        case 'progress':
          if (data && typeof data === 'object') {
            const progressData = data as SSEProgressEvent;
            useChatStreamStore.getState().setProgress(taskId, {
              progressPercent: progressData.progress_percent,
              progressText: progressData.progress_text,
              currentNode: progressData.current_node,
              currentNodeDisplay: progressData.current_node_display,
            });
          }
          break;

        case 'done':
          if (data && typeof data === 'object') {
            const doneData = data as SSEDoneEvent;
            const outputFile = doneData.output_file;
            const fileName =
              typeof outputFile === 'string' ? outputFile.split(/[\\/]/).pop() : undefined;
            handledTerminalTasksRef.current.add(taskId);
            completeTask(taskId, outputFile, fileName, getCurrentContent(taskId, true));
            clearTaskRuntime(taskId);
          }
          onCompleteRef.current?.();
          break;

        case 'error':
          if (data && typeof data === 'object') {
            const errorData = data as SSEErrorEvent;
            const errorMessage = errorData.error || 'Unknown error';
            const isFatal = errorData.is_fatal ?? true;

            handledTerminalTasksRef.current.add(taskId);

            if (!isFatal) {
              cancelTask(taskId, getCurrentContent(taskId));
              clearTaskRuntime(taskId);
              onCompleteRef.current?.();
              break;
            }

            failTask(taskId, errorMessage, getCurrentContent(taskId));
            clearTaskRuntime(taskId);
            onErrorRef.current?.(errorMessage);
          }
          break;

        default:
          break;
      }
    },
    [
      taskId,
      cancelTask,
      clearTaskRuntime,
      completeTask,
      failTask,
      getCurrentContent,
      normalizeLogLevel,
      parseTimestamp,
      rememberEventId,
    ]
  );

  useEffect(() => {
    handledTerminalTasksRef.current.clear();
  }, [taskId]);

  useEffect(() => {
    let isActive = true;

    if (!taskId) {
      queueMicrotask(() => {
        if (!isActive) {
          return;
        }
        setConnectionTaskId(null);
        setConnectionLastEventId(null);
      });
      return () => {
        isActive = false;
      };
    }

    const locatedMessage = useChatStore.getState().findMessageByTaskId(taskId);
    if (!locatedMessage) {
      queueMicrotask(() => {
        if (isActive) {
          discardStaleTaskRuntime(taskId);
        }
      });
      return () => {
        isActive = false;
      };
    }

    if (locatedMessage.message.status !== 'generating') {
      clearTaskRuntime(taskId);
      return () => {
        isActive = false;
      };
    }

    useChatStreamStore.getState().ensureStream(taskId);
    useChatTaskSessionStore.getState().upsertSession(taskId);

    const hydrateConnection = async () => {
      if (isActive) {
        setConnectionTaskId(null);
        setConnectionLastEventId(null);
      }

      const stream = useChatStreamStore.getState().streams[taskId];
      const session = useChatTaskSessionStore.getState().sessions[taskId];
      const streamIsEmpty =
        !stream ||
        (stream.content.logs.length === 0 && !stream.content.aiContent.text.trim());

      const connectWith = (lastEventId: string | null) => {
        if (!isActive) {
          return;
        }
        setConnectionLastEventId(lastEventId);
        setConnectionTaskId(taskId);
      };

      if (streamIsEmpty) {
        useChatStreamStore.getState().replaceStream(taskId);
      }

      try {
        const task = await getTaskStatus(taskId);
        if (!isActive) {
          return;
        }

        if (
          task.status === 'completed' ||
          task.status === 'failed' ||
          task.status === 'cancelled'
        ) {
          if (streamIsEmpty) {
            connectWith(null);
          } else {
            finalizeFromTaskStatus(taskId, task);
          }
          return;
        }

        connectWith(streamIsEmpty ? null : stream?.lastEventId || session?.lastEventId || null);
      } catch (error) {
        if (!isActive) {
          return;
        }
        if (
          typeof error === 'object' &&
          error !== null &&
          (((error as { code?: string }).code === 'TASK_NOT_FOUND') ||
            ((error as { status?: number }).status === 404))
        ) {
          discardStaleTaskRuntime(taskId);
          return;
        }
        connectWith(streamIsEmpty ? null : stream?.lastEventId || session?.lastEventId || null);
      }
    };

    void hydrateConnection();

    return () => {
      isActive = false;
    };
  }, [clearTaskRuntime, discardStaleTaskRuntime, finalizeFromTaskStatus, taskId]);

  const { isConnected, error, close, reconnect } = useSSE({
    endpoint: connectionTaskId ? `/api/stream/${connectionTaskId}` : '',
    autoConnect: !!connectionTaskId,
    autoReconnect: true,
    heartbeatTimeout: 45000,
    lastEventId: connectionLastEventId,
    onMessage: handleMessage,
  });

  return {
    isConnected,
    error,
    close,
    reconnect,
  };
}

export default useChatSSE;
