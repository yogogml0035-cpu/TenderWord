import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FormPanel } from '@/components/chat/FormPanel';
import { useChatStore } from '@/stores/chatStore';
import type { TenderData } from '@/types/api';

const mockUseTaskHeartbeat = jest.fn();
const mockUseCurrentConversationTaskStatus = jest.fn();
const mockCreateGenerateTask = jest.fn();
const mockGetTaskStatus = jest.fn();
const mockCancelTaskApi = jest.fn();
const mockConvertXjcgFormToApiRequest = jest.fn();
const mockConvertGngkFormToApiRequest = jest.fn();

const mockTenderData: TenderData = {
  project_name: '测试项目',
  project_number: 'TEST-001',
  project_content: '测试内容',
  bzj_rule: '测试保证金规则',
  buyer_name: '测试采购人',
  project_zbr_xbr: '张三',
  zbr_xbr_tel: '13800138000',
  zbr_pinyin: 'zhangsan',
  shell_start_date: '2024-01-01',
  shell_end_date: '2024-12-31',
  submit_date: '2024-12-31',
  platform: '测试平台',
  service_fee: '1000',
};

const mockXjcgFormData = {
  tender_no: 'XJCG-001',
  tender_data: mockTenderData,
  model: 'deepseek' as const,
  files: {
    clean_draft: {
      id: 'clean-id',
      file_path: 'D:/UploadFiles/clean.docx',
      file_name: 'clean.docx',
      original_name: 'clean.docx',
      size: 1024,
      upload_time: '2024-01-01T00:00:00.000Z',
    },
    tender_params: [
      {
        id: 'params-id',
        file_path: 'D:/UploadFiles/params.docx',
        file_name: 'params.docx',
        original_name: 'params.docx',
        size: 1024,
        upload_time: '2024-01-01T00:00:00.000Z',
      },
    ],
  },
  insertion_config: {
    before_text: '第三章  采购需求',
    after_text: '第四章  响应文件有关格式',
  },
};

const mockGngkFormData = {
  ...mockXjcgFormData,
  tender_no: 'GNGK-001',
  insertion_config: {
    before_text: '第三章 招标内容及要求',
    after_text: '第四章 投标文件有关格式',
  },
};

jest.mock('@/hooks/useHydrated', () => ({
  useHydrated: () => true,
}));

jest.mock('@/hooks/useChatSSE', () => ({
  useChatSSE: jest.fn(),
}));

jest.mock('@/hooks/useTaskHeartbeat', () => ({
  useTaskHeartbeat: (...args: unknown[]) => mockUseTaskHeartbeat(...args),
}));

jest.mock('@/hooks/useCurrentConversationTaskStatus', () => ({
  useCurrentConversationTaskStatus: (...args: unknown[]) =>
    mockUseCurrentConversationTaskStatus(...args),
}));

jest.mock('@/lib/api', () => ({
  createGenerateTask: (...args: unknown[]) => mockCreateGenerateTask(...args),
  getTaskStatus: (...args: unknown[]) => mockGetTaskStatus(...args),
  cancelTask: (...args: unknown[]) => mockCancelTaskApi(...args),
}));

jest.mock('@/lib/formDataConverter', () => ({
  convertXjcgFormToApiRequest: (...args: unknown[]) =>
    mockConvertXjcgFormToApiRequest(...args),
  convertGngkFormToApiRequest: (...args: unknown[]) =>
    mockConvertGngkFormToApiRequest(...args),
}));

jest.mock('@/components/forms/XjcgTenderForm', () => ({
  XjcgTenderForm: ({
    isSubmitting,
    canCancel,
    onSubmit,
    onCancel,
  }: {
    isSubmitting?: boolean;
    canCancel?: boolean;
    onSubmit: (data: typeof mockXjcgFormData) => Promise<void> | void;
    onCancel?: () => Promise<void> | void;
  }) => (
    <div
      data-testid="xjcg-form"
      data-submitting={isSubmitting ? 'true' : 'false'}
      data-can-cancel={canCancel ? 'true' : 'false'}
    >
      XjcgTenderForm
      <button type="button" aria-label="提交XJCG表单" onClick={() => void onSubmit(mockXjcgFormData)}>
        提交XJCG
      </button>
      {canCancel ? (
        <button type="button" aria-label="取消XJCG任务" onClick={() => void onCancel?.()}>
          取消XJCG
        </button>
      ) : null}
    </div>
  ),
}));

jest.mock('@/components/forms/GngkTenderForm', () => ({
  GngkTenderForm: ({
    isSubmitting,
    canCancel,
    onSubmit,
    onCancel,
  }: {
    isSubmitting?: boolean;
    canCancel?: boolean;
    onSubmit: (data: typeof mockGngkFormData) => Promise<void> | void;
    onCancel?: () => Promise<void> | void;
  }) => (
    <div
      data-testid="gngk-form"
      data-submitting={isSubmitting ? 'true' : 'false'}
      data-can-cancel={canCancel ? 'true' : 'false'}
    >
      GngkTenderForm
      <button type="button" aria-label="提交GNGK表单" onClick={() => void onSubmit(mockGngkFormData)}>
        提交GNGK
      </button>
      {canCancel ? (
        <button type="button" aria-label="取消GNGK任务" onClick={() => void onCancel?.()}>
          取消GNGK
        </button>
      ) : null}
    </div>
  ),
}));

describe('FormPanel', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();

    mockUseTaskHeartbeat.mockClear();
    mockUseCurrentConversationTaskStatus.mockReset();
    mockCreateGenerateTask.mockReset();
    mockGetTaskStatus.mockReset();
    mockCancelTaskApi.mockReset();
    mockConvertXjcgFormToApiRequest.mockReset();
    mockConvertGngkFormToApiRequest.mockReset();

    mockUseCurrentConversationTaskStatus.mockReturnValue({
      currentTaskId: null,
      currentTaskSummary: null,
      currentTaskStatus: null,
      waitingCount: undefined,
      isCurrentTaskQueued: false,
      isCurrentTaskRunning: false,
      runningTaskProgress: null,
    });

    mockConvertXjcgFormToApiRequest.mockReturnValue({
      form_type: 'xjcg_tender',
      tender_data: mockTenderData,
      file_paths: {
        clean_draft: 'D:/UploadFiles/clean.docx',
        tender_params: ['D:/UploadFiles/params.docx'],
      },
      insertion_config: mockXjcgFormData.insertion_config,
      model: 'deepseek',
    });
    mockConvertGngkFormToApiRequest.mockReturnValue({
      form_type: 'gngk_tender',
      tender_data: mockTenderData,
      file_paths: {
        clean_draft: 'D:/UploadFiles/clean.docx',
        tender_params: ['D:/UploadFiles/params.docx'],
      },
      insertion_config: mockGngkFormData.insertion_config,
      model: 'deepseek',
    });

    mockCreateGenerateTask.mockResolvedValue({
      task_id: 'task-created',
      status: 'queued',
      queue_position: 1,
      waiting_count: 0,
    });

    mockGetTaskStatus.mockResolvedValue({
      task_id: 'task-created',
      status: 'queued',
      progress: {
        completed_nodes: [],
        running_nodes: [],
        completed_count: 0,
        total_nodes: 10,
        progress_percent: 0,
      },
    });

    mockCancelTaskApi.mockResolvedValue({
      success: true,
      task_id: 'task-running',
      message: '任务已取消',
      was_running: true,
      noop: false,
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
    expect(mockUseTaskHeartbeat.mock.calls[0]?.[1]).toEqual(
      expect.objectContaining({
        onMissingTask: expect.any(Function),
        onTerminalState: expect.any(Function),
      })
    );
  });

  it('interrupts stale tasks immediately when heartbeat reports task not found', () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          currentTaskId: 'task-running',
        },
      ],
      activeTaskIds: ['task-running'],
      taskSummaries: {
        'task-running': {
          task_id: 'task-running',
          status: 'running',
          updated_at: Date.now(),
        },
      },
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

    const heartbeatOptions = mockUseTaskHeartbeat.mock.calls[0]?.[1] as
      | { onMissingTask?: (taskId: string) => void }
      | undefined;

    act(() => {
      heartbeatOptions?.onMissingTask?.('task-running');
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    expect(conversation?.currentTaskId).toBeUndefined();
    expect(useChatStore.getState().activeTaskIds).toEqual([]);
  });

  it('renders gngk form via registry mapping when tenderType is gngk', () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          tenderType: 'gngk',
        },
      ],
      selectedTenderType: 'gngk',
    }));

    render(<FormPanel />);

    expect(screen.getByTestId('gngk-form')).toBeInTheDocument();
    expect(screen.queryByTestId('xjcg-form')).not.toBeInTheDocument();
    expect(screen.getByText('国内公开')).toBeInTheDocument();
  });

  it('uses xjcg converter mapping when submitting xjcg form', async () => {
    const user = userEvent.setup();
    render(<FormPanel />);

    await user.click(screen.getByRole('button', { name: '提交XJCG表单' }));

    await waitFor(() => {
      expect(mockConvertXjcgFormToApiRequest).toHaveBeenCalledWith(mockXjcgFormData);
      expect(mockCreateGenerateTask).toHaveBeenCalledWith({
        ...mockConvertXjcgFormToApiRequest.mock.results[0]?.value,
        conversation_id: 'conv-1',
      });
    });
    expect(mockConvertGngkFormToApiRequest).not.toHaveBeenCalled();
  });

  it('uses gngk converter mapping when submitting gngk form', async () => {
    const user = userEvent.setup();
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          tenderType: 'gngk',
        },
      ],
      selectedTenderType: 'gngk',
    }));

    render(<FormPanel />);

    await user.click(screen.getByRole('button', { name: '提交GNGK表单' }));

    await waitFor(() => {
      expect(mockConvertGngkFormToApiRequest).toHaveBeenCalledWith(mockGngkFormData);
      expect(mockCreateGenerateTask).toHaveBeenCalledWith({
        ...mockConvertGngkFormToApiRequest.mock.results[0]?.value,
        conversation_id: 'conv-1',
      });
    });
    expect(mockConvertXjcgFormToApiRequest).not.toHaveBeenCalled();
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
    expect(screen.getByRole('status')).toHaveTextContent('系统正在建立生成任务与进度流');
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

  it('calls cancel API through form cancel flow when current task is cancellable', async () => {
    const user = userEvent.setup();
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
      runningTaskProgress: {
        completed_count: 1,
        total_nodes: 5,
        progress_percent: 20,
      },
    });

    render(<FormPanel />);

    await user.click(screen.getByRole('button', { name: '取消XJCG任务' }));

    await waitFor(() => {
      expect(mockCancelTaskApi).toHaveBeenCalledWith('task-running');
    });
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
