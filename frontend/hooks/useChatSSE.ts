'use client';

import { useCallback, useRef } from 'react';
import { useChatStore } from '@/stores/chatStore';
import { useSSE } from './useSSE';
import type { LogEntry, DualColumnContent } from '@/types/chat';

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
  
  // Refs to track current content for incremental updates
  const currentContentRef = useRef<DualColumnContent>({
    logs: [],
    aiContent: {
      text: '',
      timestamp: Date.now(),
      isComplete: false,
    },
  });

  const handleMessage = useCallback((sseMessage: { event: string; data: unknown }) => {
    if (!conversationId || !messageId) return;

    const { event, data } = sseMessage;

    switch (event) {
      case 'log':
        // Add log entry to left column
        if (data && typeof data === 'object') {
          const logData = data as Record<string, unknown>;
          const logEntry: LogEntry = {
            id: `log_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`,
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
        // Progress updates - could be extended to update a progress field
        if (data && typeof data === 'object') {
          const progressData = data as Record<string, unknown>;
          console.log('Progress update:', progressData);
        }
        break;

      case 'done':
        // Task completed
        if (taskId) {
          const doneData = data && typeof data === 'object' ? data as Record<string, unknown> : {};
          completeTask(
            taskId,
            doneData.output_file as string | undefined,
            doneData.file_name as string | undefined
          );
        }
        onComplete?.();
        break;

      case 'error':
        // Task failed
        const errorData = data && typeof data === 'object' ? data as Record<string, unknown> : {};
        const errorMessage = (errorData.message as string) || 'Unknown error';
        if (taskId) {
          failTask(taskId, errorMessage);
        }
        onError?.(errorMessage);
        break;

      case 'status':
        // Status updates
        if (data && typeof data === 'object') {
          const statusData = data as Record<string, unknown>;
          console.log('Status update:', statusData);
        }
        break;

      default:
        // Handle any unknown event types
        console.log('Unknown SSE event:', event, data);
    }
  }, [conversationId, messageId, taskId, updateMessage, completeTask, failTask, onComplete, onError]);

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
