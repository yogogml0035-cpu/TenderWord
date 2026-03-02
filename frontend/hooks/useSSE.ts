'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  createSSEConnection,
  closeSSEConnection,
  type SSEConnection,
  type SSEMessage,
  type SSEOptions,
} from '@/lib/sse';

export interface SSEHookState {
  /** Whether the connection is currently open */
  isConnected: boolean;
  /** Whether currently attempting to reconnect */
  isReconnecting: boolean;
  /** Number of reconnection attempts made */
  reconnectAttempts: number;
  /** Error message if connection failed */
  error: string | null;
}

export interface SSEHookReturn extends SSEHookState {
  /** Close the connection */
  close: () => void;
  /** Manually reconnect */
  reconnect: () => void;
  /** Latest message received */
  lastMessage: SSEMessage | null;
  /** All messages received */
  messages: SSEMessage[];
  /** Clear message history */
  clearMessages: () => void;
}

export interface UseSSEOptions extends SSEOptions {
  /** Endpoint URL path (e.g., '/api/stream/task-123') */
  endpoint: string;
  /** Whether to connect immediately on mount */
  autoConnect?: boolean;
  /** Maximum number of messages to keep in history */
  maxMessageHistory?: number;
}

/**
 * React Hook for SSE connections with auto-reconnect
 * 
 * @example
 * ```tsx
 * function TaskProgress({ taskId }: { taskId: string }) {
 *   const { isConnected, lastMessage, close } = useSSE({
 *     endpoint: `/api/stream/${taskId}`,
 *     onMessage: (msg) => console.log(msg),
 *   });
 * 
 *   return (
 *     <div>
 *       {isConnected ? 'Connected' : 'Disconnected'}
 *       {lastMessage && <pre>{JSON.stringify(lastMessage)}</pre>}
 *     </div>
 *   );
 * }
 * ```
 */
export function useSSE(options: UseSSEOptions): SSEHookReturn {
  const {
    endpoint,
    autoConnect = true,
    maxMessageHistory = 100,
    onMessage,
    onError,
    onOpen,
    onClose,
    onReconnect,
    ...sseOptions
  } = options;

  const connectionRef = useRef<SSEConnection | null>(null);
  const [state, setState] = useState<SSEHookState>({
    isConnected: false,
    isReconnecting: false,
    reconnectAttempts: 0,
    error: null,
  });
  const [messages, setMessages] = useState<SSEMessage[]>([]);
  const [lastMessage, setLastMessage] = useState<SSEMessage | null>(null);

  const addMessage = useCallback((message: SSEMessage) => {
    setLastMessage(message);
    setMessages((prev) => {
      const newMessages = [...prev, message];
      if (newMessages.length > maxMessageHistory) {
        return newMessages.slice(newMessages.length - maxMessageHistory);
      }
      return newMessages;
    });
  }, [maxMessageHistory]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setLastMessage(null);
  }, []);

  const close = useCallback(() => {
    if (connectionRef.current) {
      closeSSEConnection(connectionRef.current);
      connectionRef.current = null;
    }
    setState((prev) => ({
      ...prev,
      isConnected: false,
      isReconnecting: false,
    }));
  }, []);

  const connect = useCallback(() => {
    // Close existing connection
    close();

    setState({
      isConnected: false,
      isReconnecting: false,
      reconnectAttempts: 0,
      error: null,
    });

    connectionRef.current = createSSEConnection(endpoint, {
      ...sseOptions,
      onOpen: () => {
        setState((prev) => ({
          ...prev,
          isConnected: true,
          isReconnecting: false,
          error: null,
        }));
        onOpen?.();
      },
      onMessage: (message) => {
        addMessage(message);
        onMessage?.(message);
      },
      onError: (error) => {
        setState((prev) => ({
          ...prev,
          isConnected: false,
          error: error instanceof ErrorEvent ? error.message : 'Connection error',
        }));
        onError?.(error);
      },
      onClose: () => {
        setState((prev) => ({
          ...prev,
          isConnected: false,
          isReconnecting: false,
        }));
        onClose?.();
      },
      onReconnect: (attempt) => {
        setState((prev) => ({
          ...prev,
          isReconnecting: true,
          reconnectAttempts: attempt,
        }));
        onReconnect?.(attempt);
      },
    });
  }, [endpoint, sseOptions, onMessage, onError, onOpen, onClose, onReconnect, close, addMessage]);

  const reconnect = useCallback(() => {
    connect();
  }, [connect]);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      close();
    };
  }, [autoConnect, connect, close]);

  // Reconnect when endpoint changes
  useEffect(() => {
    if (autoConnect && connectionRef.current) {
      connect();
    }
  }, [endpoint, autoConnect, connect]);

  return {
    ...state,
    close,
    reconnect,
    lastMessage,
    messages,
    clearMessages,
  };
}

/**
 * Hook for tracking task progress via SSE
 * 
 * @example
 * ```tsx
 * function TaskMonitor({ taskId }: { taskId: string }) {
 *   const { progress, logs, llmOutput, status } = useTaskProgress(taskId);
 *   
 *   return (
 *     <div>
 *       <ProgressBar value={progress} />
 *       <LogViewer logs={logs} />
 *     </div>
 *   );
 * }
 * ```
 */
export function useTaskProgress(taskId: string | null) {
  const [progress, setProgress] = useState({
    completedCount: 0,
    totalNodes: 0,
    progressPercent: 0,
    currentNode: '',
    currentNodeDisplay: '',
  });
  const [logs, setLogs] = useState<Array<{ timestamp: string; level: string; message: string; node?: string }>>([]);
  const [llmOutput, setLlmOutput] = useState('');
  const [status, setStatus] = useState<'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | null>(null);
  const [result, setResult] = useState<{ output_file?: string; file_name?: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { isConnected, close } = useSSE({
    endpoint: taskId ? `/api/stream/${taskId}` : '',
    autoConnect: !!taskId,
    onMessage: (message) => {
      switch (message.event) {
        case 'progress':
          if (typeof message.data === 'object' && message.data !== null) {
            const data = message.data as Record<string, unknown>;
            setProgress({
              completedCount: (data.completed_count as number) || 0,
              totalNodes: (data.total_nodes as number) || 0,
              progressPercent: (data.progress_percent as number) || 0,
              currentNode: (data.node as string) || '',
              currentNodeDisplay: (data.current_node_display as string) || '',
            });
          }
          break;

        case 'log':
          if (typeof message.data === 'object' && message.data !== null) {
            const data = message.data as Record<string, unknown>;
            setLogs((prev) => [
              ...prev,
              {
                timestamp: (data.timestamp as string) || new Date().toISOString(),
                level: (data.level as string) || 'INFO',
                message: (data.message as string) || '',
                node: data.node as string | undefined,
              },
            ]);
          }
          break;

        case 'llm':
          if (typeof message.data === 'object' && message.data !== null) {
            const data = message.data as Record<string, unknown>;
            const content = (data.content as string) || '';
            const isComplete = data.is_complete as boolean;
            
            if (isComplete) {
              // LLM generation complete
            } else {
              setLlmOutput((prev) => prev + content);
            }
          }
          break;

        case 'status':
          if (typeof message.data === 'object' && message.data !== null) {
            const data = message.data as Record<string, unknown>;
            setStatus((data.status as typeof status) || null);
            if (data.result && typeof data.result === 'object') {
              setResult(data.result as typeof result);
            }
          }
          break;

        case 'error':
          if (typeof message.data === 'object' && message.data !== null) {
            const data = message.data as Record<string, unknown>;
            setError((data.message as string) || 'Unknown error');
            setStatus('failed');
          }
          break;

        case 'done':
          if (typeof message.data === 'object' && message.data !== null) {
            const data = message.data as Record<string, unknown>;
            setStatus((data.status as typeof status) || 'completed');
            close();
          }
          break;
      }
    },
  });

  return {
    isConnected,
    progress,
    logs,
    llmOutput,
    status,
    result,
    error,
    close,
  };
}

export default useSSE;
