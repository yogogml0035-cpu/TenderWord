import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ChatPanel } from '@/components/chat/ChatPanel';
import { cancelTask, streamUserMessage } from '@/lib/api';
import { useChatStore } from '@/stores/chatStore';
import { useChatStreamStore } from '@/stores/chatStreamStore';
import type { UserStreamEvent } from '@/types/api';
import type { Message } from '@/types/chat';

jest.mock('@/lib/api', () => {
  const actual = jest.requireActual('@/lib/api');
  return {
    ...actual,
    cancelTask: jest.fn(),
    downloadFile: jest.fn(),
    streamUserMessage: jest.fn(),
  };
});

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
    onCancel,
    onSend,
  }: {
    value?: string;
    disabled?: boolean;
    loading?: boolean;
    placeholder?: string;
    selectedModel?: string;
    onModelChange?: (model: string) => void;
    onCancel?: () => void;
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
      <button type="button" data-testid="cancel-chat-button" onClick={() => onCancel?.()}>
        cancel chat
      </button>
    </div>
  ),
}));

const mockStreamUserMessage = streamUserMessage as jest.MockedFunction<typeof streamUserMessage>;
const mockCancelTask = cancelTask as jest.MockedFunction<typeof cancelTask>;

function mockUserStream(events: UserStreamEvent[], terminalError?: unknown) {
  mockStreamUserMessage.mockImplementationOnce(async (_payload, options = {}) => {
    for (const event of events) {
      await options.onEvent?.(event);
    }
    if (terminalError) {
      throw terminalError;
    }
  });
}

describe('ChatPanel', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    mockStreamUserMessage.mockReset();
    mockCancelTask.mockReset();
    mockCancelTask.mockResolvedValue({
      success: true,
      task_id: 'task-1',
      message: '任务已取消',
      was_running: true,
    });

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

    mockUserStream([
      { event: 'route', data: { route: 'reply' } },
      { event: 'done', data: { content: '重试成功内容' } },
    ]);

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('retry-message-button'));

    await waitFor(() => {
      const conversation = useChatStore.getState().conversations[0];
      expect(conversation.messages).toHaveLength(1);
      expect(conversation.messages[0].id).toBe('msg-ai-failed');
      expect(conversation.messages[0].status).toBe('completed');
      expect(conversation.messages[0].content).toBe('重试成功内容');
    });

    expect(mockStreamUserMessage).toHaveBeenCalledTimes(1);
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

    mockUserStream([
      { event: 'route', data: { route: 'rewrite' } },
      {
        event: 'task_accepted',
        data: {
          task_id: 'task-rewrite',
          task_kind: 'rewrite',
          status: 'queued',
          queue_position: 0,
          waiting_count: 0,
        },
      },
    ]);

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

    expect(mockStreamUserMessage).toHaveBeenCalledTimes(1);
    expect(mockStreamUserMessage.mock.calls[0]?.[0]).toMatchObject({
      conversation_id: 'conv-1',
      model: 'deepseek',
      messages: [{ role: 'user', content: '请帮我修改这一段内容' }],
    });
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

    mockUserStream([
      { event: 'route', data: { route: 'reply' } },
      { event: 'done', data: { content: '你好，请问有什么可以帮你？' } },
    ]);

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('send-current-input-button'));

    await waitFor(() => {
      const conversation = useChatStore.getState().conversations[0];
      expect(conversation.currentTaskId).toBeUndefined();
      expect(conversation.messages).toHaveLength(2);
      expect(conversation.messages[1].type).toBe('ai');
      expect(conversation.messages[1].status).toBe('completed');
    });
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

    mockUserStream([
      { event: 'route', data: { route: 'reply' } },
      { event: 'done', data: { content: '好的，我继续说明。' } },
    ]);

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('send-current-input-button'));

    await waitFor(() => {
      expect(mockStreamUserMessage).toHaveBeenCalledTimes(1);
    });

    expect(mockStreamUserMessage.mock.calls[0]?.[0].messages).toEqual([
      { role: 'user', content: '继续帮我解释一下' },
    ]);
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

    mockUserStream([
      { event: 'route', data: { route: 'rewrite' } },
      {
        event: 'error',
        data: {
          message: '修改任务创建失败',
        },
      },
    ]);

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
  });

  it('cancels an active normal chat stream through the shared AbortSignal path', async () => {
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
          chat_input: '帮我写一段说明',
        },
      },
    }));

    mockStreamUserMessage.mockImplementationOnce(
      async (_payload, options = {}) =>
        new Promise<void>((_resolve, reject) => {
          void (async () => {
            await options.onEvent?.({ event: 'route', data: { route: 'reply' } });
            await options.onEvent?.({ event: 'chunk', data: { content: '正在生成中' } });
          })();
          options.signal?.addEventListener(
            'abort',
            () => reject(new DOMException('Aborted', 'AbortError')),
            { once: true }
          );
        })
    );

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('send-current-input-button'));

    await waitFor(() => {
      const conversation = useChatStore.getState().conversations[0];
      expect(conversation.messages[1]).toMatchObject({
        type: 'ai',
        status: 'generating',
        content: '正在生成中',
      });
    });

    fireEvent.click(screen.getByTestId('cancel-chat-button'));

    await waitFor(() => {
      const conversation = useChatStore.getState().conversations[0];
      expect(conversation.messages[1]).toMatchObject({
        type: 'ai',
        status: 'cancelled',
        content: '正在生成中',
      });
    });
  });
});
