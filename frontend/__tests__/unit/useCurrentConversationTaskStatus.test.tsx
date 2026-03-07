import { renderHook, waitFor } from '@testing-library/react';
import { useCurrentConversationTaskStatus } from '@/hooks/useCurrentConversationTaskStatus';
import { getTaskList, getTaskStatus } from '@/lib/api';
import { useChatStore } from '@/stores/chatStore';

jest.mock('@/lib/api', () => ({
  getTaskStatus: jest.fn(),
  getTaskList: jest.fn(),
}));

const mockGetTaskStatus = getTaskStatus as jest.MockedFunction<typeof getTaskStatus>;
const mockGetTaskList = getTaskList as jest.MockedFunction<typeof getTaskList>;

function resetStore() {
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
        currentTaskId: 'task-queued',
        messages: [],
      },
    ],
    currentConversationId: 'conv-1',
    activeTaskIds: ['task-queued'],
    taskMessageMap: {},
    taskSummaries: {},
    isLoading: false,
    error: null,
    selectedTenderType: 'xjcg',
  }));
}

describe('useCurrentConversationTaskStatus', () => {
  beforeEach(() => {
    resetStore();
    jest.clearAllMocks();
  });

  it('prefers current_running_progress from task detail and normalizes missing percent fields', async () => {
    mockGetTaskStatus.mockResolvedValue({
      task_id: 'task-queued',
      status: 'queued',
      created_at: new Date().toISOString(),
      queue_position: 1,
      waiting_count: 1,
      progress: {
        completed_nodes: [],
        running_nodes: [],
        completed_count: 0,
        total_nodes: 7,
        progress_text: '0/7',
        progress_percent: 0,
      },
      current_running_progress: {
        task_id: 'task-running',
        status: 'running',
        completed_nodes: ['prepare_template'],
        running_nodes: ['extract_tender_params'],
        current_node: 'extract_tender_params',
        current_node_display: '提取原始采购需求',
        completed_count: 1,
        total_nodes: 10,
      } as never,
    } as never);

    const { result } = renderHook(() => useCurrentConversationTaskStatus(60000));

    await waitFor(() => {
      expect(result.current.runningTaskProgress).toEqual({
        completed_count: 1,
        total_nodes: 10,
        progress_percent: 10,
        progress_text: '1/10',
      });
    });

    expect(mockGetTaskList).not.toHaveBeenCalled();
  });

  it('does not fall back when the backend explicitly reports no active running task', async () => {
    mockGetTaskStatus.mockResolvedValue({
      task_id: 'task-queued',
      status: 'queued',
      created_at: new Date().toISOString(),
      queue_position: 1,
      waiting_count: 1,
      progress: {
        completed_nodes: [],
        running_nodes: [],
        completed_count: 0,
        total_nodes: 7,
        progress_text: '0/7',
        progress_percent: 0,
      },
      current_running_progress: null,
    } as never);

    const { result } = renderHook(() => useCurrentConversationTaskStatus(60000));

    await waitFor(() => {
      expect(mockGetTaskStatus).toHaveBeenCalledWith('task-queued');
    });

    expect(result.current.runningTaskProgress).toBeNull();
    expect(mockGetTaskList).not.toHaveBeenCalled();
  });

  it('falls back to the running task list only when current_running_progress is missing', async () => {
    mockGetTaskStatus.mockResolvedValue({
      task_id: 'task-queued',
      status: 'queued',
      created_at: new Date().toISOString(),
      queue_position: 1,
      waiting_count: 1,
      progress: {
        completed_nodes: [],
        running_nodes: [],
        completed_count: 0,
        total_nodes: 7,
        progress_text: '0/7',
        progress_percent: 0,
      },
    } as never);
    mockGetTaskList.mockResolvedValue({
      success: true,
      total: 1,
      tasks: [
        {
          task_id: 'task-running',
          status: 'running',
          created_at: new Date().toISOString(),
          progress: {
            completed_nodes: ['prepare_template'],
            running_nodes: ['extract_tender_params'],
            current_node: 'extract_tender_params',
            completed_count: 1,
            total_nodes: 7,
          },
        } as never,
      ],
    });

    const { result } = renderHook(() => useCurrentConversationTaskStatus(60000));

    await waitFor(() => {
      expect(result.current.runningTaskProgress?.completed_count).toBe(1);
      expect(result.current.runningTaskProgress?.total_nodes).toBe(7);
      expect(result.current.runningTaskProgress?.progress_text).toBe('1/7');
      expect(result.current.runningTaskProgress?.progress_percent).toBeCloseTo(14.2857142857, 5);
    });

    expect(mockGetTaskList).toHaveBeenCalledWith({ status: 'running' });
  });
});
