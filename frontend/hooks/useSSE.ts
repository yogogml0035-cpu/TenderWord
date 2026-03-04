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
    autoReconnect,
    maxReconnectAttempts,
    reconnectDelay,
    reconnectDelayMultiplier,
    maxReconnectDelay,
    heartbeatTimeout,
  } = options;

  // Use ref for stable connection management
  const connectionRef = useRef<SSEConnection | null>(null);
  
  // Store callbacks in refs to avoid dependency issues
  const callbacksRef = useRef({
    onMessage,
    onError,
    onOpen,
    onClose,
    onReconnect,
  });
  
  // Update refs when callbacks change
  useEffect(() => {
    callbacksRef.current = {
      onMessage,
      onError,
      onOpen,
      onClose,
      onReconnect,
    };
  }, [onMessage, onError, onOpen, onClose, onReconnect]);
  
  // Store config options in ref
  const optionsRef = useRef({
    autoReconnect,
    maxReconnectAttempts,
    reconnectDelay,
    reconnectDelayMultiplier,
    maxReconnectDelay,
    heartbeatTimeout,
  });
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

  // Track if component is mounted
  const isMountedRef = useRef(true);
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
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

    const callbacks = callbacksRef.current;
    const opts = optionsRef.current;

    connectionRef.current = createSSEConnection(endpoint, {
      ...opts,
      onOpen: () => {
        if (!isMountedRef.current) return;
        setState((prev) => ({
          ...prev,
          isConnected: true,
          isReconnecting: false,
          error: null,
        }));
        callbacks.onOpen?.();
      },
      onMessage: (message) => {
        if (!isMountedRef.current) return;
        addMessage(message);
        callbacks.onMessage?.(message);
      },
      onError: (error) => {
        if (!isMountedRef.current) return;
        setState((prev) => ({
          ...prev,
          isConnected: false,
          error: error instanceof ErrorEvent ? error.message : 'Connection error',
        }));
        callbacks.onError?.(error);
      },
      onClose: () => {
        if (!isMountedRef.current) return;
        setState((prev) => ({
          ...prev,
          isConnected: false,
          isReconnecting: false,
        }));
        callbacks.onClose?.();
      },
      onReconnect: (attempt) => {
        if (!isMountedRef.current) return;
        setState((prev) => ({
          ...prev,
          isReconnecting: true,
          reconnectAttempts: attempt,
        }));
        callbacks.onReconnect?.(attempt);
      },
    });
  }, [endpoint, close, addMessage]);

  const reconnect = useCallback(() => {
    connect();
  }, [connect]);

  // Auto-connect on mount
  useEffect(() => {
    if (!autoConnect) return;
    
    const timeoutId = setTimeout(() => {
      connect();
    }, 0);

    return () => {
      clearTimeout(timeoutId);
      close();
    };
  }, [autoConnect, connect, close]);

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
