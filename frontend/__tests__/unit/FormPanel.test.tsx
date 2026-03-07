import { render, screen } from '@testing-library/react';
import { FormPanel } from '@/components/chat/FormPanel';
import { useChatStore } from '@/stores/chatStore';

jest.mock('@/hooks/useHydrated', () => ({
  useHydrated: () => true,
}));

jest.mock('@/hooks/useChatSSE', () => ({
  useChatSSE: jest.fn(),
}));

const mockUseTaskHeartbeat = jest.fn();
jest.mock('@/hooks/useTaskHeartbeat', () => ({
  useTaskHeartbeat: (...args: unknown[]) => mockUseTaskHeartbeat(...args),
}));

const mockUseCurrentConversationTaskStatus = jest.fn();
jest.mock('@/hooks/useCurrentConversationTaskStatus', () => ({
  useCurrentConversationTaskStatus: (...args: unknown[]) =>
    mockUseCurrentConversationTaskStatus(...args),
}));

jest.mock('@/components/forms/XjcgTenderForm', () => ({
  XjcgTenderForm: ({
    isSubmitting,
    canCancel,
  }: {
    isSubmitting?: boolean;
    canCancel?: boolean;
  }) => (
    <div
      data-testid="xjcg-form"
      data-submitting={isSubmitting ? 'true' : 'false'}
      data-can-cancel={canCancel ? 'true' : 'false'}
    >
      XjcgTenderForm
    </div>
  ),
}));

jest.mock('@/components/forms/GngkTenderForm', () => ({
  GngkTenderForm: ({
    isSubmitting,
    canCancel,
  }: {
    isSubmitting?: boolean;
    canCancel?: boolean;
  }) => (
    <div
      data-testid="gngk-form"
      data-submitting={isSubmitting ? 'true' : 'false'}
      data-can-cancel={canCancel ? 'true' : 'false'}
    >
      GngkTenderForm
    </div>
  ),
}));

describe('FormPanel', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    mockUseTaskHeartbeat.mockClear();
    mockUseCurrentConversationTaskStatus.mockReset();
    mockUseCurrentConversationTaskStatus.mockReturnValue({
      currentTaskId: null,
      currentTaskSummary: null,
      currentTaskStatus: null,
      waitingCount: undefined,
      isCurrentTaskQueued: false,
      isCurrentTaskRunning: false,
      runningTaskProgress: null,
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
        },
      ],
      currentConversationId: 'conv-1',
      activeTaskIds: ['task-queued', 'task-running'],
      taskMessageMap: {},
      selectedTenderType: 'xjcg',
      isLoading: false,
      error: null,
    }));
  });

  it('keeps heartbeats alive for all active tasks even when the current conversation has no active task', () => {
    render(<FormPanel />);

    expect(screen.getByText('XjcgTenderForm')).toBeInTheDocument();
    expect(mockUseTaskHeartbeat.mock.calls[0]?.[0]).toEqual(['task-queued', 'task-running']);
  });

  it('shows queue status card and keeps form locked/cancellable when current task is queued', () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          currentTaskId: 'task-queued',
        },
      ],
      activeTaskIds: ['task-queued'],
    }));
    mockUseCurrentConversationTaskStatus.mockReturnValue({
      currentTaskId: 'task-queued',
      currentTaskSummary: {
        task_id: 'task-queued',
        status: 'queued',
        waiting_count: 2,
        updated_at: Date.now(),
      },
      currentTaskStatus: 'queued',
      waitingCount: 2,
      isCurrentTaskQueued: true,
      isCurrentTaskRunning: false,
      runningTaskProgress: {
        completed_count: 1,
        total_nodes: 10,
        progress_percent: 10,
      },
    });

    render(<FormPanel />);

    expect(screen.getByText('任务排队中')).toBeInTheDocument();
    expect(screen.getByText('前方等待2个任务（含当前执行任务）')).toBeInTheDocument();
    expect(screen.getByText('当前执行任务进度：1/10（10%）')).toBeInTheDocument();
    expect(screen.getByTestId('xjcg-form')).toHaveAttribute('data-submitting', 'true');
    expect(screen.getByTestId('xjcg-form')).toHaveAttribute('data-can-cancel', 'true');
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('shows queue fallback copy when there is no active running progress snapshot yet', () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          currentTaskId: 'task-queued',
        },
      ],
      activeTaskIds: ['task-queued'],
    }));
    mockUseCurrentConversationTaskStatus.mockReturnValue({
      currentTaskId: 'task-queued',
      currentTaskSummary: {
        task_id: 'task-queued',
        status: 'queued',
        waiting_count: 1,
        updated_at: Date.now(),
      },
      currentTaskStatus: 'queued',
      waitingCount: 1,
      isCurrentTaskQueued: true,
      isCurrentTaskRunning: false,
      runningTaskProgress: null,
    });

    render(<FormPanel />);

    expect(screen.getByText('当前暂无执行任务，即将开始下一任务')).toBeInTheDocument();
    expect(screen.queryByText(/获取中/)).not.toBeInTheDocument();
  });

  it('shows running overlay when current task is running', () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          currentTaskId: 'task-running',
        },
      ],
      activeTaskIds: ['task-running'],
    }));
    mockUseCurrentConversationTaskStatus.mockReturnValue({
      currentTaskId: 'task-running',
      currentTaskSummary: {
        task_id: 'task-running',
        status: 'running',
        updated_at: Date.now(),
      },
      currentTaskStatus: 'running',
      waitingCount: undefined,
      isCurrentTaskQueued: false,
      isCurrentTaskRunning: true,
      runningTaskProgress: null,
    });

    render(<FormPanel />);

    expect(screen.getByRole('status')).toHaveTextContent('正在生成招标文档...');
    expect(screen.getByTestId('xjcg-form')).toHaveAttribute('data-submitting', 'true');
    expect(screen.getByTestId('xjcg-form')).toHaveAttribute('data-can-cancel', 'true');
  });
});
