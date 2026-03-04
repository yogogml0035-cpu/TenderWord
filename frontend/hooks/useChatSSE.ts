'use client';

import { useCallback, useEffect, useRef } from 'react';
import { useChatStore } from '@/stores/chatStore';
import { useSSE } from './useSSE';
import type { LogEntry, DualColumnContent } from '@/types/chat';
import { generateLogEntryId } from '@/lib/chat-utils';

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
  const { updateMessage, completeTask, failTask } = useChatStore();

  // Initialize content ref lazily to avoid calling Date.now during render
  const initContentRef = useCallback(
    () => ({
      logs: [],
      aiContent: {
        text: '',
        timestamp: Date.now(),
        isComplete: false,
      },
    }),
    []
  );

  const currentContentRef = useRef<DualColumnContent>(initContentRef());

  useEffect(() => {
    currentContentRef.current = initContentRef();
  }, [taskId, messageId, initContentRef]);

  const handleMessage = useCallback(
    (sseMessage: { event: string; data: unknown }) => {
      if (!conversationId || !messageId) return;

      const { event, data } = sseMessage;

      switch (event) {
        case 'log':
          // Add log entry to left column
          if (data && typeof data === 'object') {
            const logData = data as Record<string, unknown>;
            const logEntry: LogEntry = {
              id: generateLogEntryId(),
              timestamp: Date.now(),
              level: (logData.level as LogEntry['level']) || 'info',
              message: (logData.message as string) || '',
              node: logData.node as string | undefined,
            };

            currentContentRef.current = {
              ...currentContentRef.current,
              logs: [...currentContentRef.current.logs, logEntry],
            };

            updateMessage(conversationId, messageId, {
              content: currentContentRef.current,
            });
          }
          break;

        case 'llm':
          // Append to AI content in right column
          if (data && typeof data === 'object') {
            const llmData = data as Record<string, unknown>;
            const newText = (llmData.content as string) || '';
            const isComplete = (llmData.is_complete as boolean) || false;

            currentContentRef.current = {
              ...currentContentRef.current,
              aiContent: {
                text: currentContentRef.current.aiContent.text + newText,
                timestamp: Date.now(),
                isComplete,
              },
            };

            updateMessage(conversationId, messageId, {
              content: currentContentRef.current,
            });
          }
          break;

        case 'progress':
          if (data && typeof data === 'object') {
            const progressData = data as Record<string, unknown>;
            updateMessage(conversationId, messageId, {
              metadata: {
                progressPercent: progressData.progress_percent as number | undefined,
                progressText: progressData.progress_text as string | undefined,
                currentNode: progressData.current_node as string | undefined,
                currentNodeDisplay: progressData.current_node_display as string | undefined,
              },
            });
          }
          break;

        case 'done':
          // Task completed
          if (taskId) {
            const doneData =
              data && typeof data === 'object' ? (data as Record<string, unknown>) : {};
            const outputFile = doneData.output_file as string | undefined;
            const fileName =
              typeof outputFile === 'string' ? outputFile.split(/[\\/]/).pop() : undefined;
            completeTask(taskId, outputFile, fileName);
          }
          onComplete?.();
          break;

        case 'error':
          // Task failed
          const errorData =
            data && typeof data === 'object' ? (data as Record<string, unknown>) : {};
          const errorMessage = (errorData.error as string) || 'Unknown error';
          if (taskId) {
            failTask(taskId, errorMessage);
          }
          onError?.(errorMessage);
          break;

        default:
          break;
      }
    },
    [conversationId, messageId, taskId, updateMessage, completeTask, failTask, onComplete, onError]
  );

  const { isConnected, error, close, reconnect } = useSSE({
    endpoint: taskId ? `/api/stream/${taskId}` : '',
    autoConnect: !!taskId,
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
