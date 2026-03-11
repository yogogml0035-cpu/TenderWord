import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ChatPanel } from '@/components/chat/ChatPanel';
import { useChatStore } from '@/stores/chatStore';
import { useChatStreamStore } from '@/stores/chatStreamStore';
import type { Message } from '@/types/chat';

jest.mock('@/hooks/useHydrated', () => ({
  useHydrated: () => true,
}));

jest.mock('@/components/chat/MessageList', () => ({
  MessageList: ({
    messages,
    emptyState,
    onRetry,
  }: {
    messages: Array<unknown>;
    emptyState?: unknown;
    onRetry?: (message: Message) => void;
  }) => (
    <div data-testid="message-list">
      {messages.length === 0 ? (
        emptyState ? (
          <div data-testid="custom-empty">custom-empty</div>
        ) : (
          <div data-testid="default-empty">default-empty</div>
        )
      ) : (
        <div data-testid="message-count">{messages.length}</div>
      )}
      {onRetry && messages.length > 0 && (
        <button
          type="button"
          data-testid="retry-message-button"
          onClick={() => onRetry(messages[0] as Message)}
        >
          retry message
        </button>
      )}
    </div>
  ),
}));

jest.mock('@/components/chat/ChatInput', () => ({
  ChatInput: ({
    value,
    disabled,
    loading,
    placeholder,
    selectedModel,
    onModelChange,
    onSend,
  }: {
    value?: string;
    disabled?: boolean;
    loading?: boolean;
    placeholder?: string;
    selectedModel?: string;
    onModelChange?: (model: string) => void;
    onSend?: (message: string) => void;
  }) => (
    <div
      data-testid="chat-input"
      data-disabled={disabled ? 'true' : 'false'}
      data-loading={loading ? 'true' : 'false'}
      data-placeholder={placeholder || ''}
      data-model={selectedModel || ''}
    >
      <button type="button" data-testid="change-model-button" onClick={() => onModelChange?.('qwen')}>
        change model
      </button>
      <button
        type="button"
        data-testid="send-current-input-button"
        onClick={() => onSend?.(value || 'default message')}
      >
        send current input
      </button>
    </div>
  ),
}));

describe('ChatPanel', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();

    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          id: 'conv-1',
          title: '0811-DSITC253505',
          tenderType: 'xjcg',
          createdAt: 1,
          updatedAt: 1,
          messages: [],
          currentTaskId: 'task-1',
        },
      ],
      currentConversationId: 'conv-1',
      activeTaskIds: ['task-1'],
      taskMessageMap: {},
      conversationDrafts: {},
      taskSummaries: {
        'task-1': {
          task_id: 'task-1',
          status: 'queued',
          waiting_count: 2,
          updated_at: Date.now(),
        },
      },
      selectedTenderType: 'xjcg',
      isLoading: false,
      error: null,
    }));
    useChatStreamStore.setState({ streams: {} });
  });

  it('suppresses the default empty state while queued without showing a top status bar', () => {
    render(<ChatPanel />);

    expect(
      screen.queryByText('排队中，轮到当前任务后将开始显示进度日志')
    ).not.toBeInTheDocument();
    expect(screen.getByTestId('custom-empty')).toBeInTheDocument();
    expect(screen.queryByTestId('default-empty')).not.toBeInTheDocument();
    expect(screen.getByTestId('chat-input')).toHaveAttribute('data-model', 'deepseek');
  });

  it('does not show queue status bar for running conversation', () => {
    useChatStore.setState((state) => ({
      ...state,
      taskSummaries: {
        'task-1': {
          task_id: 'task-1',
          status: 'running',
          updated_at: Date.now(),
        },
      },
    }));

    render(<ChatPanel />);

    expect(
      screen.queryByText('排队中，轮到当前任务后将开始显示进度日志')
    ).not.toBeInTheDocument();
  });

  it('suppresses the default empty state while starting without showing a top status bar', () => {
    useChatStore.setState((state) => ({
      ...state,
      taskSummaries: {
        'task-1': {
          task_id: 'task-1',
          status: 'queued',
          waiting_count: 0,
          updated_at: Date.now(),
        },
      },
    }));

    render(<ChatPanel />);

    expect(screen.queryByText('排队中，轮到当前任务后将开始显示进度日志')).not.toBeInTheDocument();
    expect(screen.queryByText('正在启动任务，稍后将显示进度日志')).not.toBeInTheDocument();
    expect(screen.getByTestId('custom-empty')).toBeInTheDocument();
  });

  it('uses the conversation draft model when present', () => {
    useChatStore.setState((state) => ({
      ...state,
      conversationDrafts: {
        'conv-1': {
          model: 'doubao',
        },
      },
    }));

    render(<ChatPanel />);

    expect(screen.getByTestId('chat-input')).toHaveAttribute('data-model', 'doubao');
  });

  it('updates the current conversation draft when model changes from chat input', () => {
    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('change-model-button'));

    expect(useChatStore.getState().getConversationDraft('conv-1')?.model).toBe('qwen');
  });

  it('does not expose a rewrite toggle in chat input', () => {
    render(<ChatPanel />);

    expect(screen.queryByTestId('toggle-rewrite-button')).not.toBeInTheDocument();
    expect(screen.getByTestId('chat-input')).toHaveAttribute('data-placeholder', '回复生成中，请稍候...');
  });

  it('retries failed ai message in place instead of appending a new bubble', async () => {
    const failedMessage: Message = {
      id: 'msg-ai-failed',
      conversationId: 'conv-1',
      type: 'ai',
      content: '旧的失败内容',
      timestamp: Date.now(),
      status: 'error',
      metadata: {
        chatKind: 'normal',
        chatPrompt: '请重试',
        chatModel: 'qwen',
      },
    };

    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          currentTaskId: undefined,
          messages: [failedMessage],
        },
      ],
      activeTaskIds: [],
      taskSummaries: {},
    }));

    const encoder = new TextEncoder();
    const streamPayload = `${JSON.stringify({ event: 'done', data: { content: '重试成功内容' } })}\n`;
    const originalFetch = (globalThis as { fetch?: typeof fetch }).fetch;
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => {
          let consumed = false;
          return {
            read: async () => {
              if (consumed) {
                return { value: undefined, done: true };
              }
              consumed = true;
              return { value: encoder.encode(streamPayload), done: false };
            },
          };
        },
      },
    } as unknown as Response);
    (globalThis as { fetch?: typeof fetch }).fetch = fetchMock as unknown as typeof fetch;

    try {
      render(<ChatPanel />);

      fireEvent.click(screen.getByTestId('retry-message-button'));

      await waitFor(() => {
        const conversation = useChatStore.getState().conversations[0];
        expect(conversation.messages).toHaveLength(1);
        expect(conversation.messages[0].id).toBe('msg-ai-failed');
        expect(conversation.messages[0].status).toBe('completed');
        expect(conversation.messages[0].content).toBe('重试成功内容');
      });

      expect(fetchMock).toHaveBeenCalledTimes(1);
    } finally {
      (globalThis as { fetch?: typeof fetch }).fetch = originalFetch;
    }
  });

  it('auto routes rewrite-like input in normal mode to rewrite task flow', async () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          currentTaskId: undefined,
        },
      ],
      activeTaskIds: [],
      taskSummaries: {},
      conversationDrafts: {
        'conv-1': {
          chat_input: '请帮我修改这一段内容',
        },
      },
    }));

    const encoder = new TextEncoder();
    const streamPayload = [
      JSON.stringify({ event: 'route', data: { route: 'rewrite' } }),
      JSON.stringify({
        event: 'task_accepted',
        data: {
          task_id: 'task-rewrite',
          task_kind: 'rewrite',
          status: 'queued',
          queue_position: 0,
          waiting_count: 0,
        },
      }),
    ].join('\n') + '\n';
    const originalFetch = (globalThis as { fetch?: typeof fetch }).fetch;
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => {
          let consumed = false;
          return {
            read: async () => {
              if (consumed) {
                return { value: undefined, done: true };
              }
              consumed = true;
              return { value: encoder.encode(streamPayload), done: false };
            },
          };
        },
      },
    } as unknown as Response);
    (globalThis as { fetch?: typeof fetch }).fetch = fetchMock as unknown as typeof fetch;

    try {
      render(<ChatPanel />);

      fireEvent.click(screen.getByTestId('send-current-input-button'));

      await waitFor(() => {
        const conversation = useChatStore.getState().conversations[0];
        const draft = useChatStore.getState().getConversationDraft('conv-1');
        expect(conversation.currentTaskId).toBe('task-rewrite');
        expect(draft?.pending_rewrite_task_id).toBe('task-rewrite');
        expect(conversation.messages).toHaveLength(2);
        expect(conversation.messages[0].metadata?.chatKind).toBe('rewrite');
        expect(conversation.messages[1]).toMatchObject({
          type: 'ai',
          content: '正在创建修改重写任务',
          status: 'completed',
          metadata: {
            chatKind: 'rewrite',
          },
        });
      });

      expect(fetchMock).toHaveBeenCalled();
      expect(fetchMock.mock.calls[0][0]).toContain('/api/user/stream');
    } finally {
      (globalThis as { fetch?: typeof fetch }).fetch = originalFetch;
    }
  });

  it('keeps ordinary chat on the streaming path without creating a task', async () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          currentTaskId: undefined,
        },
      ],
      activeTaskIds: [],
      taskSummaries: {},
      conversationDrafts: {
        'conv-1': {
          chat_input: '你好',
        },
      },
    }));

    const encoder = new TextEncoder();
    const streamPayload =
      JSON.stringify({ event: 'done', data: { content: '你好，请问有什么可以帮你？' } }) + '\n';
    const originalFetch = (globalThis as { fetch?: typeof fetch }).fetch;
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => {
          let consumed = false;
          return {
            read: async () => {
              if (consumed) {
                return { value: undefined, done: true };
              }
              consumed = true;
              return { value: encoder.encode(streamPayload), done: false };
            },
          };
        },
      },
    } as unknown as Response);
    (globalThis as { fetch?: typeof fetch }).fetch = fetchMock as unknown as typeof fetch;

    try {
      render(<ChatPanel />);

      fireEvent.click(screen.getByTestId('send-current-input-button'));

      await waitFor(() => {
        const conversation = useChatStore.getState().conversations[0];
        expect(conversation.currentTaskId).toBeUndefined();
        expect(conversation.messages).toHaveLength(2);
        expect(conversation.messages[1].type).toBe('ai');
        expect(conversation.messages[1].status).toBe('completed');
      });
    } finally {
      (globalThis as { fetch?: typeof fetch }).fetch = originalFetch;
    }
  });

  it('excludes task-notice ai bubbles from normal chat context', async () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          currentTaskId: undefined,
          messages: [
            {
              id: 'msg-task-notice',
              conversationId: 'conv-1',
              type: 'ai',
              content: '正在创建生成招标文件任务',
              timestamp: Date.now(),
              status: 'completed',
              metadata: {
                chatKind: 'task-notice',
              },
            },
          ],
        },
      ],
      activeTaskIds: [],
      taskSummaries: {},
      conversationDrafts: {
        'conv-1': {
          chat_input: '继续帮我解释一下',
        },
      },
    }));

    const encoder = new TextEncoder();
    const streamPayload =
      JSON.stringify({ event: 'done', data: { content: '好的，我继续说明。' } }) + '\n';
    const originalFetch = (globalThis as { fetch?: typeof fetch }).fetch;
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => {
          let consumed = false;
          return {
            read: async () => {
              if (consumed) {
                return { value: undefined, done: true };
              }
              consumed = true;
              return { value: encoder.encode(streamPayload), done: false };
            },
          };
        },
      },
    } as unknown as Response);
    (globalThis as { fetch?: typeof fetch }).fetch = fetchMock as unknown as typeof fetch;

    try {
      render(<ChatPanel />);

      fireEvent.click(screen.getByTestId('send-current-input-button'));

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledTimes(1);
      });

      const requestInit = fetchMock.mock.calls[0]?.[1] as RequestInit | undefined;
      const body =
        requestInit && typeof requestInit.body === 'string'
          ? JSON.parse(requestInit.body)
          : null;

      expect(body?.messages).toEqual([{ role: 'user', content: '继续帮我解释一下' }]);
    } finally {
      (globalThis as { fetch?: typeof fetch }).fetch = originalFetch;
    }
  });

  it('removes the rewrite placeholder bubble when the rewrite stream fails before task acceptance', async () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          currentTaskId: undefined,
        },
      ],
      activeTaskIds: [],
      taskSummaries: {},
      conversationDrafts: {
        'conv-1': {
          chat_input: '请帮我修改这一段内容',
        },
      },
    }));

    const encoder = new TextEncoder();
    const streamPayload = [
      JSON.stringify({ event: 'route', data: { route: 'rewrite' } }),
      JSON.stringify({
        event: 'error',
        data: {
          message: '修改任务创建失败',
        },
      }),
    ].join('\n') + '\n';
    const originalFetch = (globalThis as { fetch?: typeof fetch }).fetch;
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => {
          let consumed = false;
          return {
            read: async () => {
              if (consumed) {
                return { value: undefined, done: true };
              }
              consumed = true;
              return { value: encoder.encode(streamPayload), done: false };
            },
          };
        },
      },
    } as unknown as Response);
    (globalThis as { fetch?: typeof fetch }).fetch = fetchMock as unknown as typeof fetch;

    try {
      render(<ChatPanel />);

      fireEvent.click(screen.getByTestId('send-current-input-button'));

      await waitFor(() => {
        const conversation = useChatStore.getState().conversations[0];
        expect(conversation.currentTaskId).toBeUndefined();
        expect(conversation.messages).toHaveLength(2);
        expect(conversation.messages[0]).toMatchObject({
          type: 'user',
          metadata: {
            chatKind: 'rewrite',
          },
        });
        expect(conversation.messages[1]).toMatchObject({
          type: 'system',
          content: '修改任务创建失败',
          status: 'completed',
        });
        expect(conversation.messages.find((message) => message.content === '正在创建修改重写任务')).toBeUndefined();
      });
    } finally {
      (globalThis as { fetch?: typeof fetch }).fetch = originalFetch;
    }
  });
});
