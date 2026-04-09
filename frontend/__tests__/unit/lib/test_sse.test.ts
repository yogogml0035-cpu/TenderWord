import { createSSEConnection } from '@/lib/sse';

class MockEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  static instances: MockEventSource[] = [];

  onopen: ((event?: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  readyState = MockEventSource.CONNECTING;
  readonly url: string;
  private readonly listeners = new Map<string, Array<(event: Event) => void>>();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(event: string, handler: (event: Event) => void) {
    const handlers = this.listeners.get(event) || [];
    handlers.push(handler);
    this.listeners.set(event, handlers);
  }

  close() {
    this.readyState = MockEventSource.CLOSED;
  }

  emitError(event: Event = new Event('error')) {
    this.onerror?.(event);
  }
}

describe('createSSEConnection', () => {
  const originalEventSource = global.EventSource;
  const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;

  beforeEach(() => {
    jest.useFakeTimers();
    MockEventSource.instances = [];
    global.EventSource = MockEventSource as unknown as typeof EventSource;
  });

  afterEach(() => {
    jest.useRealTimers();
    global.EventSource = originalEventSource;
    process.env.NEXT_PUBLIC_API_URL = originalApiUrl;
    jest.restoreAllMocks();
  });

  it('selects a single valid API base URL when NEXT_PUBLIC_API_URL contains multiple candidates', () => {
    process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000,http://10.11.1.99:8000';

    createSSEConnection('/api/stream/task-1');

    expect(MockEventSource.instances[0]?.url).toBe('http://localhost:8000/api/stream/task-1');
  });

  it('does not log or reconnect when the server closes the stream normally', () => {
    const onClose = jest.fn();
    const onReconnect = jest.fn();
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    createSSEConnection('/api/stream/task-1', {
      autoReconnect: true,
      onClose,
      onReconnect,
    });

    const source = MockEventSource.instances[0];
    source.readyState = MockEventSource.CLOSED;
    source.emitError();

    jest.runOnlyPendingTimers();

    expect(consoleErrorSpy).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onReconnect).not.toHaveBeenCalled();
  });

  it('does not log or reconnect after the client has already closed the stream', () => {
    const onReconnect = jest.fn();
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    const connection = createSSEConnection('/api/stream/task-1', {
      autoReconnect: true,
      onReconnect,
    });

    const source = MockEventSource.instances[0];
    connection.close();
    source.emitError();

    jest.runOnlyPendingTimers();

    expect(consoleErrorSpy).not.toHaveBeenCalled();
    expect(onReconnect).not.toHaveBeenCalled();
  });
});
