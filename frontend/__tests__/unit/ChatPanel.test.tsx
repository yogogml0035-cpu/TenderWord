import { render, screen } from '@testing-library/react';
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
  }: {
    disabled?: boolean;
    loading?: boolean;
    placeholder?: string;
  }) => (
    <div
      data-testid="chat-input"
      data-disabled={disabled ? 'true' : 'false'}
      data-loading={loading ? 'true' : 'false'}
      data-placeholder={placeholder || ''}
    />
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

  it('shows top queue status bar and suppresses default empty state while queued', () => {
    render(<ChatPanel />);

    expect(screen.getByText('排队中，轮到当前任务后将开始显示进度日志')).toBeInTheDocument();
    expect(screen.getByTestId('custom-empty')).toBeInTheDocument();
    expect(screen.queryByTestId('default-empty')).not.toBeInTheDocument();
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
});
