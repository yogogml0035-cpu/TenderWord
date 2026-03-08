import { fireEvent, render, screen } from '@testing-library/react';
import { ChatPanel } from '@/components/chat/ChatPanel';
import { useChatStore } from '@/stores/chatStore';
import { useChatStreamStore } from '@/stores/chatStreamStore';

jest.mock('@/hooks/useHydrated', () => ({
  useHydrated: () => true,
}));

jest.mock('@/components/chat/MessageList', () => ({
  MessageList: ({
    messages,
    emptyState,
  }: {
    messages: Array<unknown>;
    emptyState?: unknown;
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
    </div>
  ),
}));

jest.mock('@/components/chat/ChatInput', () => ({
  ChatInput: ({
    disabled,
    loading,
    placeholder,
    selectedModel,
    onModelChange,
  }: {
    disabled?: boolean;
    loading?: boolean;
    placeholder?: string;
    selectedModel?: string;
    onModelChange?: (model: string) => void;
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
});
