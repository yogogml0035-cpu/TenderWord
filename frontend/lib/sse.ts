/**
 * SSE (Server-Sent Events) client for real-time updates
 * Features: Auto-reconnect, Last-Event-ID support, heartbeat detection
 */

import { resolveApiBaseUrl } from '@/lib/apiBaseUrl';

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
  /** Seed Last-Event-ID for late join or refresh recovery */
  lastEventId?: string | null;
}

export interface SSEConnection {
  eventSource: EventSource;
  close: () => void;
  reconnect: () => void;
}

interface SSEState {
  eventSource: EventSource | null;
  lastEventId: string | null;
  seenEventIds: Set<string>;
  reconnectAttempts: number;
  reconnectTimer: NodeJS.Timeout | null;
  heartbeatTimer: NodeJS.Timeout | null;
  isClosed: boolean;
  closeNotified: boolean;
}

const MAX_SEEN_EVENT_IDS = 5000;

const DEFAULT_OPTIONS: Required<
  Pick<
    SSEOptions,
    | 'autoReconnect'
    | 'maxReconnectAttempts'
    | 'reconnectDelay'
    | 'reconnectDelayMultiplier'
    | 'maxReconnectDelay'
    | 'heartbeatTimeout'
  >
> = {
  autoReconnect: false,
  maxReconnectAttempts: 5,
  reconnectDelay: 1000,
  reconnectDelayMultiplier: 1.5,
  maxReconnectDelay: 30000,
  heartbeatTimeout: 0,
};

/**
 * Create SSE connection with auto-reconnect support
 */
export function createSSEConnection(endpoint: string, options: SSEOptions = {}): SSEConnection {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  const state: SSEState = {
    eventSource: null,
    lastEventId: opts.lastEventId ?? null,
    seenEventIds: new Set<string>(),
    reconnectAttempts: 0,
    reconnectTimer: null,
    heartbeatTimer: null,
    isClosed: false,
    closeNotified: false,
  };

  const apiUrl = resolveApiBaseUrl();

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

  const notifyClose = () => {
    if (state.closeNotified) {
      return;
    }
    state.closeNotified = true;
    opts.onClose?.();
  };

  const setupHeartbeat = () => {
    if (opts.heartbeatTimeout <= 0) {
      return;
    }
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
    state.closeNotified = false;
    if (state.eventSource) {
      state.eventSource.close();
      state.eventSource = null;
    }

    // Build URL with Last-Event-ID header support via query param
    let url = `${apiUrl}${endpoint}`;
    if (state.lastEventId) {
      url +=
        (url.includes('?') ? '&' : '?') + `lastEventId=${encodeURIComponent(state.lastEventId)}`;
    }

    const eventSource = new EventSource(url);
    state.eventSource = eventSource;

    const parseEventData = (rawData: string): unknown => {
      try {
        return JSON.parse(rawData);
      } catch {
        return rawData;
      }
    };

    const rememberEventId = (eventId?: string): boolean => {
      if (!eventId) return false;
      if (state.seenEventIds.has(eventId)) {
        return true;
      }
      state.seenEventIds.add(eventId);
      state.lastEventId = eventId;

      while (state.seenEventIds.size > MAX_SEEN_EVENT_IDS) {
        const oldest = state.seenEventIds.values().next().value;
        if (!oldest) break;
        state.seenEventIds.delete(oldest);
      }
      return false;
    };

    const emitMessage = (eventName: string, event: MessageEvent) => {
      setupHeartbeat();
      const eventId = event.lastEventId || undefined;
      if (rememberEventId(eventId)) {
        return;
      }
      opts.onMessage?.({
        event: eventName,
        data: parseEventData(event.data),
        id: eventId,
      });
    };

    eventSource.onopen = () => {
      console.log('[SSE] Connection opened');
      state.reconnectAttempts = 0;
      opts.onOpen?.();
      setupHeartbeat();
    };

    eventSource.onmessage = (event: MessageEvent) => {
      emitMessage(event.type, event);
    };

    // Listen for specific events
    eventSource.addEventListener('connected', (event) => {
      emitMessage('connected', event as MessageEvent);
    });

    eventSource.addEventListener('log', (event) => {
      emitMessage('log', event as MessageEvent);
    });

    eventSource.addEventListener('llm', (event) => {
      emitMessage('llm', event as MessageEvent);
    });

    eventSource.addEventListener('progress', (event) => {
      emitMessage('progress', event as MessageEvent);
    });

    eventSource.addEventListener('agent_step', (event) => {
      emitMessage('agent_step', event as MessageEvent);
    });

    eventSource.addEventListener('status', (event) => {
      emitMessage('status', event as MessageEvent);
    });

    eventSource.addEventListener('error', (event: MessageEvent) => {
      emitMessage('error', event);
    });

    eventSource.addEventListener('done', (event) => {
      emitMessage('done', event as MessageEvent);
    });

    eventSource.addEventListener('heartbeat', (event) => {
      setupHeartbeat();
      const messageEvent = event as MessageEvent;
      const eventId = messageEvent.lastEventId || undefined;
      if (rememberEventId(eventId)) {
        return;
      }
      opts.onMessage?.({
        event: 'heartbeat',
        data: parseEventData(messageEvent.data),
        id: eventId,
      });
    });

    eventSource.onerror = (error) => {
      if (state.isClosed || eventSource.readyState === EventSource.CLOSED) {
        notifyClose();
        return;
      }

      console.error('[SSE] Connection error:', error);
      opts.onError?.(error);

      // Auto-reconnect logic
      if (opts.autoReconnect && !state.isClosed) {
        if (state.reconnectAttempts < opts.maxReconnectAttempts) {
          state.reconnectAttempts++;
          const delay = Math.min(
            opts.reconnectDelay *
              Math.pow(opts.reconnectDelayMultiplier, state.reconnectAttempts - 1),
            opts.maxReconnectDelay
          );

          console.log(`[SSE] Reconnecting in ${delay}ms (attempt ${state.reconnectAttempts})`);
          opts.onReconnect?.(state.reconnectAttempts);

          state.reconnectTimer = setTimeout(() => {
            if (state.eventSource) {
              state.eventSource.close();
              state.eventSource = null;
            }
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
    notifyClose();
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
