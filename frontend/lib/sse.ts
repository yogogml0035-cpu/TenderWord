/**
 * SSE (Server-Sent Events) client for real-time updates
 * Features: Auto-reconnect, Last-Event-ID support, heartbeat detection
 */

export interface SSEMessage {
  event: string;
  data: unknown;
  id?: string;
}

export interface SSEOptions {
  onMessage?: (message: SSEMessage) => void;
  onError?: (error: Event) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onReconnect?: (attempt: number) => void;
  /** Enable auto-reconnect on connection loss */
  autoReconnect?: boolean;
  /** Maximum number of reconnection attempts */
  maxReconnectAttempts?: number;
  /** Delay between reconnection attempts in ms */
  reconnectDelay?: number;
  /** Delay multiplier for exponential backoff */
  reconnectDelayMultiplier?: number;
  /** Maximum delay between reconnection attempts in ms */
  maxReconnectDelay?: number;
  /** Heartbeat timeout in ms (default: 10000) */
  heartbeatTimeout?: number;
}

export interface SSEConnection {
  eventSource: EventSource;
  close: () => void;
  reconnect: () => void;
}

interface SSEState {
  eventSource: EventSource | null;
  lastEventId: string | null;
  reconnectAttempts: number;
  reconnectTimer: NodeJS.Timeout | null;
  heartbeatTimer: NodeJS.Timeout | null;
  isClosed: boolean;
}

const DEFAULT_OPTIONS: Required<Pick<SSEOptions, 'autoReconnect' | 'maxReconnectAttempts' | 'reconnectDelay' | 'reconnectDelayMultiplier' | 'maxReconnectDelay' | 'heartbeatTimeout'>> = {
  autoReconnect: true,
  maxReconnectAttempts: 5,
  reconnectDelay: 1000,
  reconnectDelayMultiplier: 1.5,
  maxReconnectDelay: 30000,
  heartbeatTimeout: 10000,
};

/**
 * Create SSE connection with auto-reconnect support
 */
export function createSSEConnection(
  endpoint: string,
  options: SSEOptions = {}
): SSEConnection {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  const state: SSEState = {
    eventSource: null,
    lastEventId: null,
    reconnectAttempts: 0,
    reconnectTimer: null,
    heartbeatTimer: null,
    isClosed: false,
  };

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const clearTimers = () => {
    if (state.reconnectTimer) {
      clearTimeout(state.reconnectTimer);
      state.reconnectTimer = null;
    }
    if (state.heartbeatTimer) {
      clearTimeout(state.heartbeatTimer);
      state.heartbeatTimer = null;
    }
  };

  const setupHeartbeat = () => {
    if (state.heartbeatTimer) {
      clearTimeout(state.heartbeatTimer);
    }
    state.heartbeatTimer = setTimeout(() => {
      console.warn('[SSE] Heartbeat timeout, reconnecting...');
      reconnect();
    }, opts.heartbeatTimeout);
  };

  const connect = () => {
    if (state.isClosed) return;

    clearTimers();

    // Build URL with Last-Event-ID header support via query param
    let url = `${apiUrl}${endpoint}`;
    if (state.lastEventId) {
      url += (url.includes('?') ? '&' : '?') + `lastEventId=${encodeURIComponent(state.lastEventId)}`;
    }

    const eventSource = new EventSource(url);
    state.eventSource = eventSource;

    eventSource.onopen = () => {
      console.log('[SSE] Connection opened');
      state.reconnectAttempts = 0;
      opts.onOpen?.();
      setupHeartbeat();
    };

    eventSource.onmessage = (event) => {
      setupHeartbeat();

      // Update last event ID if provided
      if (event.lastEventId) {
        state.lastEventId = event.lastEventId;
      }

      // Handle heartbeat event
      if (event.type === 'heartbeat') {
        return;
      }

      try {
        const data = JSON.parse(event.data);
        opts.onMessage?.({
          event: event.type,
          data,
          id: event.lastEventId || undefined,
        });
      } catch {
        opts.onMessage?.({
          event: event.type,
          data: event.data,
          id: event.lastEventId || undefined,
        });
      }
    };

    // Listen for specific events
    eventSource.addEventListener('connected', (event) => {
      setupHeartbeat();
      try {
        const data = JSON.parse(event.data);
        opts.onMessage?.({
          event: 'connected',
          data,
          id: event.lastEventId || undefined,
        });
      } catch {
        opts.onMessage?.({
          event: 'connected',
          data: event.data,
          id: event.lastEventId || undefined,
        });
      }
    });

    eventSource.addEventListener('log', (event) => {
      setupHeartbeat();
      try {
        const data = JSON.parse(event.data);
        opts.onMessage?.({
          event: 'log',
          data,
          id: event.lastEventId || undefined,
        });
      } catch {
        opts.onMessage?.({
          event: 'log',
          data: event.data,
          id: event.lastEventId || undefined,
        });
      }
    });

    eventSource.addEventListener('llm', (event) => {
      setupHeartbeat();
      try {
        const data = JSON.parse(event.data);
        opts.onMessage?.({
          event: 'llm',
          data,
          id: event.lastEventId || undefined,
        });
      } catch {
        opts.onMessage?.({
          event: 'llm',
          data: event.data,
          id: event.lastEventId || undefined,
        });
      }
    });

    eventSource.addEventListener('progress', (event) => {
      setupHeartbeat();
      try {
        const data = JSON.parse(event.data);
        opts.onMessage?.({
          event: 'progress',
          data,
          id: event.lastEventId || undefined,
        });
      } catch {
        opts.onMessage?.({
          event: 'progress',
          data: event.data,
          id: event.lastEventId || undefined,
        });
      }
    });

    eventSource.addEventListener('status', (event) => {
      setupHeartbeat();
      try {
        const data = JSON.parse(event.data);
        opts.onMessage?.({
          event: 'status',
          data,
          id: event.lastEventId || undefined,
        });
      } catch {
        opts.onMessage?.({
          event: 'status',
          data: event.data,
          id: event.lastEventId || undefined,
        });
      }
    });

    eventSource.addEventListener('error', (event: MessageEvent) => {
      setupHeartbeat();
      try {
        const data = JSON.parse(event.data);
        opts.onMessage?.({
          event: 'error',
          data,
          id: event.lastEventId || undefined,
        });
      } catch {
        opts.onMessage?.({
          event: 'error',
          data: event.data,
          id: event.lastEventId || undefined,
        });
      }
    });

    eventSource.addEventListener('done', (event) => {
      setupHeartbeat();
      try {
        const data = JSON.parse(event.data);
        opts.onMessage?.({
          event: 'done',
          data,
          id: event.lastEventId || undefined,
        });
      } catch {
        opts.onMessage?.({
          event: 'done',
          data: event.data,
          id: event.lastEventId || undefined,
        });
      }
    });

    eventSource.addEventListener('heartbeat', () => {
      setupHeartbeat();
      opts.onMessage?.({
        event: 'heartbeat',
        data: { timestamp: new Date().toISOString() },
      });
    });

    eventSource.onerror = (error) => {
      console.error('[SSE] Connection error:', error);

      // Don't treat normal close as error
      if (eventSource.readyState === EventSource.CLOSED) {
        opts.onClose?.();
        return;
      }

      opts.onError?.(error);

      // Auto-reconnect logic
      if (opts.autoReconnect && !state.isClosed) {
        if (state.reconnectAttempts < opts.maxReconnectAttempts) {
          state.reconnectAttempts++;
          const delay = Math.min(
            opts.reconnectDelay * Math.pow(opts.reconnectDelayMultiplier, state.reconnectAttempts - 1),
            opts.maxReconnectDelay
          );

          console.log(`[SSE] Reconnecting in ${delay}ms (attempt ${state.reconnectAttempts})`);
          opts.onReconnect?.(state.reconnectAttempts);

          state.reconnectTimer = setTimeout(() => {
            connect();
          }, delay);
        } else {
          console.error('[SSE] Max reconnection attempts reached');
          close();
        }
      }
    };
  };

  const close = () => {
    state.isClosed = true;
    clearTimers();
    if (state.eventSource) {
      state.eventSource.close();
      state.eventSource = null;
    }
    opts.onClose?.();
  };

  const reconnect = () => {
    if (state.eventSource) {
      state.eventSource.close();
    }
    connect();
  };

  // Initial connection
  connect();

  return {
    get eventSource() {
      return state.eventSource!;
    },
    close,
    reconnect,
  };
}

/**
 * Close SSE connection
 */
export function closeSSEConnection(connection: SSEConnection | null): void {
  if (connection) {
    connection.close();
  }
}

/**
 * Check if EventSource is supported
 */
export function isSSESupported(): boolean {
  return typeof EventSource !== 'undefined';


}