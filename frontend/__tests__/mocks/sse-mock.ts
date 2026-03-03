/**
 * SSE Mock Utility for Testing
 * Mock Server-Sent Events connections in tests
 */

import type {
  SSELogEvent,
  SSELLMEvent,
  SSEProgressEvent,
  SSEStatusEvent,
  SSEErrorEvent,
  SSEDoneEvent,
} from '@/types/api';

/**
 * Mock SSE Connection
 * Simulates SSE connection and event emission
 */
export class SSEMock {
  private listeners: Map<string, Array<(data: unknown) => void>> = new Map();
  private isConnected = false;
  private taskId: string | null = null;
  private eventQueue: Array<{ event: string; data: unknown }> = [];
  private eventDelay: number = 0;

  /**
   * Connect to SSE endpoint
   */
  connect(taskId: string): void {
    this.taskId = taskId;
    this.isConnected = true;
    this.emit('connected', { task_id: taskId, message: 'Connected to SSE' });
  }

  /**
   * Disconnect from SSE endpoint
   */
  disconnect(): void {
    this.isConnected = false;
    this.taskId = null;
    this.removeAllListeners();
  }

  /**
   * Register event listener
   */
  on(event: string, handler: (data: unknown) => void): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)!.push(handler);
  }

  /**
   * Remove event listener
   */
  off(event: string, handler: (data: unknown) => void): void {
    const handlers = this.listeners.get(event);
    if (handlers) {
      const index = handlers.indexOf(handler);
      if (index > -1) {
        handlers.splice(index, 1);
      }
    }
  }

  /**
   * Remove all listeners
   */
  removeAllListeners(): void {
    this.listeners.clear();
  }

  /**
   * Emit event to all listeners
   */
  emit(event: string, data: unknown): void {
    const handlers = this.listeners.get(event) || [];
    handlers.forEach((handler) => {
      if (this.eventDelay > 0) {
        setTimeout(() => handler(data), this.eventDelay);
      } else {
        handler(data);
      }
    });
  }

  /**
   * Set delay between events (for async testing)
   */
  setEventDelay(ms: number): void {
    this.eventDelay = ms;
  }

  /**
   * Queue events to be emitted in sequence
   */
  queueEvent(event: string, data: unknown): void {
    this.eventQueue.push({ event, data });
  }

  /**
   * Emit all queued events
   */
  async flushQueue(): Promise<void> {
    for (const { event, data } of this.eventQueue) {
      this.emit(event, data);
      if (this.eventDelay > 0) {
        await new Promise((resolve) => setTimeout(resolve, this.eventDelay));
      }
    }
    this.eventQueue = [];
  }

  /**
   * Get connection status
   */
  get connected(): boolean {
    return this.isConnected;
  }

  /**
   * Get current task ID
   */
  get currentTaskId(): string | null {
    return this.taskId;
  }
}

/**
 * Factory for creating SSE mock instances
 */
export function createSSEMock(): SSEMock {
  return new SSEMock();
}

/**
 * Helper to create log events
 */
export function createLogEvent(
  message: string,
  level: 'INFO' | 'DEBUG' | 'WARN' | 'ERROR' = 'INFO',
  node?: string
): SSELogEvent {
  return {
    timestamp: new Date().toISOString(),
    level,
    message,
    node,
  };
}

/**
 * Helper to create LLM events
 */
export function createLLMEvent(
  content: string,
  node: string,
  isComplete: boolean = false
): SSELLMEvent {
  return {
    timestamp: new Date().toISOString(),
    node,
    content,
    is_complete: isComplete,
  };
}

/**
 * Helper to create progress events
 */
export function createProgressEvent(
  node: string,
  completedCount: number,
  totalNodes: number
): SSEProgressEvent {
  return {
    timestamp: new Date().toISOString(),
    node,
    completed_count: completedCount,
    total_nodes: totalNodes,
    progress_percent: Math.round((completedCount / totalNodes) * 100),
    current_node_display: node,
  };
}

/**
 * Helper to create status events
 */
export function createStatusEvent(
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
): SSEStatusEvent {
  return {
    timestamp: new Date().toISOString(),
    status,
  };
}

/**
 * Helper to create error events
 */
export function createErrorEvent(
  errorCode: string,
  message: string,
  details?: string
): SSEErrorEvent {
  return {
    timestamp: new Date().toISOString(),
    error_code: errorCode,
    message,
    details,
  };
}

/**
 * Helper to create done events
 */
export function createDoneEvent(
  taskId: string,
  status: 'completed' | 'failed' | 'cancelled',
  totalTimeSeconds: number
): SSEDoneEvent {
  return {
    timestamp: new Date().toISOString(),
    task_id: taskId,
    status,
    total_time_seconds: totalTimeSeconds,
  };
}

/**
 * Simulate a complete task flow with events
 */
export async function simulateTaskFlow(
  sse: SSEMock,
  taskId: string,
  options?: {
    logCount?: number;
    llmContentChunks?: string[];
    failAt?: number; // Fail at step (1 = logs, 2 = llm, 3 = progress, 4 = done)
  }
): Promise<void> {
  const { logCount = 3, llmContentChunks = ['Content chunk 1', 'Content chunk 2'], failAt } = options || {};
  const totalSteps = logCount + llmContentChunks.length + 2; // +2 for progress and done

  sse.connect(taskId);

  // Emit log events
  if (failAt !== 1) {
    for (let i = 0; i < logCount; i++) {
      sse.emit('log', createLogEvent(`Processing step ${i + 1}`));
    }
  } else {
    sse.emit('error', createErrorEvent('SYS_INTERNAL_ERROR', 'Error during log phase'));
    return;
  }

  // Emit LLM content events
  if (failAt !== 2) {
    for (let i = 0; i < llmContentChunks.length; i++) {
      const isComplete = i === llmContentChunks.length - 1;
      sse.emit('llm', createLLMEvent(llmContentChunks[i], 'generate_content', isComplete));
    }
  } else {
    sse.emit('error', createErrorEvent('LLM_SERVICE_ERROR', 'Error during LLM generation'));
    return;
  }

  // Emit progress event
  if (failAt !== 3) {
    sse.emit('progress', createProgressEvent('update_word', totalSteps - 1, totalSteps));
  } else {
    sse.emit('error', createErrorEvent('SYS_INTERNAL_ERROR', 'Error during progress phase'));
    return;
  }

  // Emit done event
  if (failAt !== 4) {
    sse.emit('done', createDoneEvent(taskId, 'completed', 60));
  } else {
    sse.emit('error', createErrorEvent('SYS_INTERNAL_ERROR', 'Error during completion'));
  }
}
