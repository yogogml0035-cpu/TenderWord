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
    expect(screen.getByRole('status')).toHaveTextContent('任务排队中');
    expect(screen.getByTestId('queue-overlay-backdrop')).toBeInTheDocument();
    expect(screen.getByTestId('queue-status-card')).toHaveClass('border-amber-300/90');
    expect(screen.getByTestId('xjcg-form')).toHaveAttribute('data-submitting', 'true');
    expect(screen.getByTestId('xjcg-form')).toHaveAttribute('data-can-cancel', 'true');
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

  it('treats queued task with no queue ahead as starting instead of queued', () => {
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
        waiting_count: 0,
        updated_at: Date.now(),
      },
      currentTaskStatus: 'queued',
      waitingCount: 0,
      isCurrentTaskQueued: true,
      isCurrentTaskRunning: false,
      runningTaskProgress: null,
    });

    render(<FormPanel />);

    expect(screen.queryByText('任务排队中')).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('正在启动生成流程...');
    expect(screen.getByRole('status')).toHaveTextContent('系统正在建立任务与进度流');
    expect(screen.getByRole('status')).toHaveTextContent('当前没有前置任务');
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
        current_node_display: '正在生成目录与章节内容',
        progress_text: '第 2 步 / 共 5 步',
        updated_at: Date.now(),
      },
      currentTaskStatus: 'running',
      waitingCount: undefined,
      isCurrentTaskQueued: false,
      isCurrentTaskRunning: true,
      runningTaskProgress: {
        completed_count: 2,
        total_nodes: 5,
        progress_percent: 40,
      },
    });

    render(<FormPanel />);

    expect(screen.getByRole('status')).toHaveTextContent('正在生成招标文档...');
    expect(screen.getByRole('status')).toHaveTextContent('正在生成目录与章节内容');
    expect(screen.getByRole('status')).toHaveTextContent('已完成 2/5 个步骤');
    expect(screen.getByTestId('running-overlay-backdrop')).toBeInTheDocument();
    expect(screen.getByTestId('running-status-card')).toHaveClass('border-blue-400/90');
    expect(screen.getByTestId('xjcg-form')).toHaveAttribute('data-submitting', 'true');
    expect(screen.getByTestId('xjcg-form')).toHaveAttribute('data-can-cancel', 'true');
  });

  it('falls back to progress_text fraction when running progress snapshot is temporarily missing', () => {
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
        current_node_display: '删除原始采购需求',
        progress_text: '3/7',
        progress_percent: 42.8571428571,
        updated_at: Date.now(),
      },
      currentTaskStatus: 'running',
      waitingCount: undefined,
      isCurrentTaskQueued: false,
      isCurrentTaskRunning: true,
      runningTaskProgress: null,
    });

    render(<FormPanel />);

    expect(screen.getByRole('status')).toHaveTextContent('已完成 3/7 个步骤');
  });
});
