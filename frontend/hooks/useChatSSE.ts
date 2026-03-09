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
  TaskKind,
  TaskStatus,
} from '@/types/api';
import type { LogEntry } from '@/types/chat';
import { useChatStore, type TaskMessageSnapshot } from '@/stores/chatStore';
import { useChatStreamStore } from '@/stores/chatStreamStore';
import { useChatTaskSessionStore } from '@/stores/chatTaskSessionStore';
import { useSSE } from './useSSE';

interface UseChatSSEOptions {
  taskId: string | null;
  taskStatus?: TaskStatus | null;
  conversationId: string | null;
  onComplete?: () => void;
  onError?: (error: string) => void;
}

function getAIContentTriggerNode(taskKind: TaskKind): string {
  return taskKind === 'rewrite' ? 'rewrite_text' : 'generate_polished_text';
}

function resolveTaskKind(taskId: string, eventTaskKind?: unknown): TaskKind {
  if (eventTaskKind === 'rewrite' || eventTaskKind === 'generate') {
    return eventTaskKind;
  }
  return useChatStore.getState().getTaskSummary(taskId)?.task_kind || 'generate';
}

function isAIContentCompletedLog(message: string, node: unknown, taskKind: TaskKind): boolean {
  if (typeof message !== 'string' || !message) {
    return false;
  }

  const triggerNode = getAIContentTriggerNode(taskKind);
  const nodeMatched =
    node === triggerNode || message.includes(`[${triggerNode}]`);
  if (!nodeMatched) {
    return false;
  }

  return message.includes('完成');
}

/**
 * Hook that maps SSE events to task-log/task-content/task-download messages.
 */
export function useChatSSE({
  taskId,
  taskStatus = null,
  conversationId,
  onComplete,
  onError,
}: UseChatSSEOptions) {
  void conversationId;
  const completeTask = useChatStore((state) => state.completeTask);
  const failTask = useChatStore((state) => state.failTask);
  const cancelTask = useChatStore((state) => state.cancelTask);
  const ensureTaskLogMessage = useChatStore((state) => state.ensureTaskLogMessage);
  const ensureTaskContentMessage = useChatStore((state) => state.ensureTaskContentMessage);
  const markTaskContentReady = useChatStore((state) => state.markTaskContentReady);
  const discardStaleTask = useChatStore((state) => state.discardStaleTask);
  const upsertTaskSummary = useChatStore((state) => state.upsertTaskSummary);
  const [connectionTaskId, setConnectionTaskId] = useState<string | null>(null);
  const [connectionLastEventId, setConnectionLastEventId] = useState<string | null>(null);
  const handledTerminalTasksRef = useRef<Set<string>>(new Set());
  const onCompleteRef = useRef<typeof onComplete>(onComplete);
  const onErrorRef = useRef<typeof onError>(onError);
  const closeRef = useRef<() => void>(() => undefined);

  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  const clearTaskRuntime = useCallback((targetTaskId: string) => {
    useChatStreamStore.getState().clearStream(targetTaskId);
    useChatTaskSessionStore.getState().removeSession(targetTaskId);
  }, []);

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
    (targetTaskId: string, forceComplete = false): TaskMessageSnapshot | undefined => {
      const stream = useChatStreamStore.getState().streams[targetTaskId];
      if (!stream) {
        return undefined;
      }

      return {
        logs: stream.logs,
        aiText: stream.aiText,
        aiComplete: forceComplete || stream.aiComplete,
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

      upsertTaskSummary(targetTaskId, {
        task_kind: task.task_kind,
        status: task.status,
        progress_percent: task.progress.progress_percent,
        progress_text: task.progress.progress_text || '',
        current_node: task.progress.current_node || '',
        current_node_display: task.progress.current_node_display || task.progress.current_node || '',
      });

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
      upsertTaskSummary,
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
      ensureTaskLogMessage(taskId, { status: 'generating' });

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

            const taskKind = resolveTaskKind(taskId);
            if (isAIContentCompletedLog(logMessage, logData.node, taskKind)) {
              const aiText = useChatStreamStore.getState().streams[taskId]?.aiText || '';
              markTaskContentReady(taskId, aiText);
            }
          }
          break;

        case 'llm':
          if (data && typeof data === 'object') {
            const llmData = data as SSELLMEvent;
            const nextText = llmData.content || '';
            const isComplete = llmData.is_complete || false;
            const contentMode = llmData.content_mode || 'snapshot';
            const llmNode = llmData.node;
            const taskKind = resolveTaskKind(taskId);
            const triggerNode = getAIContentTriggerNode(taskKind);

            if (llmNode === triggerNode) {
              ensureTaskContentMessage(taskId);
            }

            if (contentMode === 'chunk') {
              const currentText = useChatStreamStore.getState().streams[taskId]?.aiText || '';
              const mergedText = currentText + nextText;
              useChatStreamStore.getState().setAIContent(taskId, mergedText, isComplete);
              if (llmNode === triggerNode && isComplete) {
                markTaskContentReady(taskId, mergedText);
              }
            } else {
              useChatStreamStore.getState().setAIContent(taskId, nextText, isComplete);
              if (llmNode === triggerNode && isComplete) {
                markTaskContentReady(taskId, nextText);
              }
            }
          }
          break;

        case 'progress':
          if (data && typeof data === 'object') {
            const progressData = data as SSEProgressEvent;
            upsertTaskSummary(taskId, {
              task_kind: progressData.task_kind,
              status:
                progressData.status === 'running'
                  ? 'running'
                  : progressData.status,
              progress_percent: progressData.progress_percent,
              progress_text: progressData.progress_text,
              current_node: progressData.current_node || '',
              current_node_display:
                progressData.current_node_display || progressData.current_node || '',
            });
            useChatStreamStore.getState().setProgress(taskId, {
              progressPercent: progressData.progress_percent,
              progressText: progressData.progress_text,
              currentNode: progressData.current_node,
              currentNodeDisplay: progressData.current_node_display,
            });

            const triggerNode = getAIContentTriggerNode(progressData.task_kind);
            if (
              progressData.current_node === triggerNode ||
              progressData.node === triggerNode
            ) {
              ensureTaskContentMessage(taskId);
            }
          }
          break;

        case 'done':
          if (data && typeof data === 'object') {
            const doneData = data as SSEDoneEvent;
            upsertTaskSummary(taskId, {
              task_kind: doneData.task_kind,
              status: doneData.success ? 'completed' : 'failed',
            });
            const outputFile = doneData.output_file;
            const doneFileName = (doneData as { file_name?: string }).file_name;
            const fileName =
              typeof doneFileName === 'string' && doneFileName.length > 0
                ? doneFileName
                : typeof outputFile === 'string'
                  ? outputFile.split(/[\\/]/).pop()
                  : undefined;
            handledTerminalTasksRef.current.add(taskId);
            closeRef.current();
            completeTask(taskId, outputFile, fileName, getCurrentContent(taskId, true));
            clearTaskRuntime(taskId);
          }
          onCompleteRef.current?.();
          break;

        case 'error':
          if (data && typeof data === 'object') {
            const errorData = data as SSEErrorEvent;
            upsertTaskSummary(taskId, {
              task_kind: errorData.task_kind,
              status: errorData.is_fatal ? 'failed' : 'cancelled',
            });
            const errorMessage = errorData.error || 'Unknown error';
            const isFatal = errorData.is_fatal ?? true;

            handledTerminalTasksRef.current.add(taskId);

            if (!isFatal) {
              closeRef.current();
              cancelTask(taskId, getCurrentContent(taskId));
              clearTaskRuntime(taskId);
              onCompleteRef.current?.();
              break;
            }

            closeRef.current();
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
      ensureTaskLogMessage,
      ensureTaskContentMessage,
      failTask,
      getCurrentContent,
      markTaskContentReady,
      normalizeLogLevel,
      parseTimestamp,
      rememberEventId,
      upsertTaskSummary,
    ]
  );

  useEffect(() => {
    handledTerminalTasksRef.current.clear();
  }, [taskId]);

  useEffect(() => {
    let isActive = true;

    const disconnect = () => {
      if (!isActive) {
        return;
      }
      setConnectionTaskId(null);
      setConnectionLastEventId(null);
    };

    if (!taskId) {
      queueMicrotask(disconnect);
      return () => {
        isActive = false;
      };
    }

    const connectRunningTask = () => {
      const logMessageId = ensureTaskLogMessage(taskId, { status: 'generating' });
      if (!logMessageId) {
        discardStaleTaskRuntime(taskId);
        return;
      }

      useChatStreamStore.getState().ensureStream(taskId);
      useChatTaskSessionStore.getState().upsertSession(taskId);
      const stream = useChatStreamStore.getState().streams[taskId];
      const session = useChatTaskSessionStore.getState().sessions[taskId];
      const streamIsEmpty = !stream || (stream.logs.length === 0 && !stream.aiText.trim());

      if (streamIsEmpty) {
        useChatStreamStore.getState().replaceStream(taskId);
      }

      if (!isActive) {
        return;
      }

      setConnectionLastEventId(streamIsEmpty ? null : stream?.lastEventId || session?.lastEventId || null);
      setConnectionTaskId(taskId);
    };

    const finalizeWithFallback = async (status: TaskStatus) => {
      try {
        const task = await getTaskStatus(taskId);
        if (!isActive) {
          return;
        }
        finalizeFromTaskStatus(taskId, task);
        disconnect();
        return;
      } catch {
        if (!isActive) {
          return;
        }
      }

      const finalContent = getCurrentContent(taskId, status === 'completed');
      if (status === 'completed') {
        completeTask(taskId, undefined, undefined, finalContent);
        clearTaskRuntime(taskId);
        onCompleteRef.current?.();
      } else if (status === 'failed') {
        const fallbackError = '生成失败';
        failTask(taskId, fallbackError, finalContent);
        clearTaskRuntime(taskId);
        onErrorRef.current?.(fallbackError);
      } else if (status === 'cancelled') {
        cancelTask(taskId, finalContent);
        clearTaskRuntime(taskId);
        onCompleteRef.current?.();
      }
      disconnect();
    };

    const hydrateConnection = async () => {
      if (taskStatus === 'queued') {
        disconnect();
        return;
      }

      if (taskStatus === 'completed' || taskStatus === 'failed' || taskStatus === 'cancelled') {
        await finalizeWithFallback(taskStatus);
        return;
      }

      if (taskStatus === 'running') {
        connectRunningTask();
        return;
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
          finalizeFromTaskStatus(taskId, task);
          disconnect();
          return;
        }

        if (task.status === 'queued') {
          disconnect();
          return;
        }

        connectRunningTask();
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
        disconnect();
      }
    };

    void hydrateConnection();

    return () => {
      isActive = false;
    };
  }, [
    cancelTask,
    clearTaskRuntime,
    completeTask,
    discardStaleTaskRuntime,
    ensureTaskLogMessage,
    failTask,
    finalizeFromTaskStatus,
    getCurrentContent,
    taskId,
    taskStatus,
  ]);

  const { isConnected, error, close, reconnect } = useSSE({
    endpoint: connectionTaskId ? `/api/stream/${connectionTaskId}` : '',
    autoConnect: !!connectionTaskId,
    autoReconnect: true,
    heartbeatTimeout: 45000,
    lastEventId: connectionLastEventId,
    onMessage: handleMessage,
  });

  useEffect(() => {
    closeRef.current = close;
  }, [close]);

  return {
    isConnected,
    error,
    close,
    reconnect,
  };
}

export default useChatSSE;
