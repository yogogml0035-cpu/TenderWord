import { act, renderHook, waitFor } from '@testing-library/react';
import { useChatSSE } from '@/hooks/useChatSSE';
import { useSSE } from '@/hooks/useSSE';
import { getTaskStatus } from '@/lib/api';
import { useChatStore } from '@/stores/chatStore';
import { useChatStreamStore } from '@/stores/chatStreamStore';
import { useChatTaskSessionStore } from '@/stores/chatTaskSessionStore';

jest.mock('@/hooks/useSSE', () => ({
  useSSE: jest.fn(),
}));

jest.mock('@/lib/api', () => ({
  getTaskStatus: jest.fn(),
}));

const mockUseSSE = useSSE as jest.MockedFunction<typeof useSSE>;
const mockGetTaskStatus = getTaskStatus as jest.MockedFunction<typeof getTaskStatus>;

type MockSSEOptions = Parameters<typeof useSSE>[0];

function createRunningTaskStatus() {
  return {
    task_id: 'task-1',
    status: 'running' as const,
    created_at: new Date().toISOString(),
    progress: {
      completed_nodes: [],
      running_nodes: ['generate_polished_text'],
      current_node: 'generate_polished_text',
      completed_count: 1,
      total_nodes: 7,
      progress_percent: 14.3,
    },
  };
}

function resetStores() {
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
        currentTaskId: 'task-1',
        messages: [
          {
            id: 'msg-log-1',
            conversationId: 'conv-1',
            type: 'ai',
            content: '',
            timestamp: 1,
            status: 'generating',
            taskId: 'task-1',
            metadata: {
              messageKind: 'task-log',
              logs: [],
            },
          },
        ],
      },
    ],
    currentConversationId: 'conv-1',
    activeTaskIds: ['task-1'],
    taskMessageMap: {
      'task-1': {
        logMessageId: 'msg-log-1',
      },
    },
    isLoading: false,
    error: null,
    selectedTenderType: 'xjcg',
  }));

  useChatStreamStore.setState({ streams: {} });
  useChatTaskSessionStore.setState({ sessions: {} });
}

function getTaskGroup() {
  return useChatStore.getState().findTaskMessageGroup('task-1');
}

function setQueueOnlyTaskState() {
  useChatStore.setState((state) => ({
    ...state,
    conversations: [
      {
        id: 'conv-1',
        title: '0811-DSITC253505',
        tenderType: 'xjcg',
        createdAt: 1,
        updatedAt: 1,
        currentTaskId: 'task-1',
        messages: [],
      },
    ],
    currentConversationId: 'conv-1',
    activeTaskIds: ['task-1'],
    taskMessageMap: {},
  }));
  useChatStreamStore.setState({ streams: {} });
  useChatTaskSessionStore.setState({ sessions: {} });
}

describe('useChatSSE', () => {
  let latestOptions: MockSSEOptions | null;
  let latestCloseMock: jest.Mock;

  beforeEach(() => {
    resetStores();
    latestOptions = null;
    latestCloseMock = jest.fn();
    mockUseSSE.mockImplementation((options) => {
      latestOptions = options;
      return {
        isConnected: true,
        isReconnecting: false,
        reconnectAttempts: 0,
        error: null,
        close: latestCloseMock,
        reconnect: jest.fn(),
        lastMessage: null,
        messages: [],
        clearMessages: jest.fn(),
      };
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('replaces snapshot llm content in runtime state and only persists on done', async () => {
    mockGetTaskStatus.mockResolvedValue(createRunningTaskStatus());

    renderHook(() =>
      useChatSSE({
        taskId: 'task-1',
        conversationId: 'conv-1',
      })
    );

    await waitFor(() => {
      expect(mockGetTaskStatus).toHaveBeenCalledWith('task-1');
      expect(latestOptions?.endpoint).toBe('/api/stream/task-1');
    });

    act(() => {
      latestOptions?.onMessage?.({
        event: 'llm',
        id: '1',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          node: 'generate_polished_text',
          content: '你',
          content_mode: 'snapshot',
          is_complete: false,
        },
      });
      latestOptions?.onMessage?.({
        event: 'llm',
        id: '2',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          node: 'generate_polished_text',
          content: '你好',
          content_mode: 'snapshot',
          is_complete: false,
        },
      });
      latestOptions?.onMessage?.({
        event: 'llm',
        id: '3',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          node: 'generate_polished_text',
          content: '你好啊',
          content_mode: 'snapshot',
          is_complete: false,
        },
      });
    });

    expect(useChatStreamStore.getState().streams['task-1']?.aiText).toBe('你好啊');

    const generatingGroup = getTaskGroup();
    expect(generatingGroup?.contentMessage?.status).toBe('generating');
    expect(generatingGroup?.contentMessage?.content).toBe('');

    act(() => {
      latestOptions?.onMessage?.({
        event: 'done',
        id: '4',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          success: true,
          message: '任务完成',
          output_file: 'D:/UploadFiles/output.docx',
          processing_time: 12.5,
        },
      });
    });

    const completedGroup = getTaskGroup();
    expect(completedGroup?.logMessage?.status).toBe('completed');
    expect(completedGroup?.contentMessage?.status).toBe('completed');
    expect(completedGroup?.contentMessage?.content).toBe('你好啊');
    expect(completedGroup?.downloadMessage?.metadata?.outputFile).toBe('D:/UploadFiles/output.docx');
    expect(useChatStreamStore.getState().streams['task-1']).toBeUndefined();
    expect(useChatTaskSessionStore.getState().sessions['task-1']).toBeUndefined();
  });

  it('keeps SSE disconnected while queued and creates task-log only when running', async () => {
    setQueueOnlyTaskState();

    const { rerender } = renderHook(
      ({ status }: { status: 'queued' | 'running' }) =>
        useChatSSE({
          taskId: 'task-1',
          taskStatus: status,
          conversationId: 'conv-1',
        }),
      {
        initialProps: { status: 'queued' as 'queued' | 'running' },
      }
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(latestOptions?.endpoint).toBe('');
    expect(getTaskGroup()).toBeNull();

    rerender({ status: 'running' as const });

    await waitFor(() => {
      expect(latestOptions?.endpoint).toBe('/api/stream/task-1');
    });
    expect(getTaskGroup()?.logMessage?.metadata?.messageKind).toBe('task-log');
  });

  it('clears queued cancelled task without creating any chat cards', async () => {
    setQueueOnlyTaskState();
    mockGetTaskStatus.mockResolvedValue({
      task_id: 'task-1',
      status: 'cancelled',
      created_at: new Date().toISOString(),
      progress: createRunningTaskStatus().progress,
    });

    renderHook(() =>
      useChatSSE({
        taskId: 'task-1',
        taskStatus: 'cancelled',
        conversationId: 'conv-1',
      })
    );

    await waitFor(() => {
      expect(useChatStore.getState().activeTaskIds).toHaveLength(0);
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    expect(conversation?.currentTaskId).toBeUndefined();
    expect(conversation?.messages).toHaveLength(0);
    expect(useChatStore.getState().findTaskMessageGroup('task-1')).toBeNull();
  });

  it('routes log and progress events only to stream runtime state', async () => {
    mockGetTaskStatus.mockResolvedValue(createRunningTaskStatus());

    renderHook(() =>
      useChatSSE({
        taskId: 'task-1',
        conversationId: 'conv-1',
      })
    );

    await waitFor(() => {
      expect(latestOptions?.endpoint).toBe('/api/stream/task-1');
    });

    act(() => {
      latestOptions?.onMessage?.({
        event: 'log',
        id: '1',
        data: {
          timestamp: new Date('2026-03-06T13:30:23+08:00').toISOString(),
          task_id: 'task-1',
          level: 'INFO',
          message: '[replace_content] 替换最新项目信息 完成 (6/7)',
          node: 'replace_content',
        },
      });

      latestOptions?.onMessage?.({
        event: 'progress',
        id: '2',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          status: 'running',
          progress_text: '正在替换项目信息',
          current_node: 'replace_content',
          completed_count: 6,
          total_nodes: 7,
          progress_percent: 85.7,
          current_node_display: '替换最新项目信息',
        },
      });
    });

    const runtime = useChatStreamStore.getState().streams['task-1'];
    expect(runtime?.logs).toHaveLength(1);
    expect(runtime?.aiText).toBe('');
    expect(runtime?.progressPercent).toBe(85.7);
    expect(runtime?.progressText).toBe('正在替换项目信息');

    const group = getTaskGroup();
    expect(group?.logMessage?.status).toBe('generating');
    expect(group?.contentMessage).toBeUndefined();
  });

  it('creates task-content message only when progress reaches generate_polished_text', async () => {
    mockGetTaskStatus.mockResolvedValue(createRunningTaskStatus());

    renderHook(() =>
      useChatSSE({
        taskId: 'task-1',
        conversationId: 'conv-1',
      })
    );

    await waitFor(() => {
      expect(latestOptions?.endpoint).toBe('/api/stream/task-1');
    });

    expect(getTaskGroup()?.contentMessage).toBeUndefined();

    act(() => {
      latestOptions?.onMessage?.({
        event: 'progress',
        id: '2',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          status: 'running',
          progress_text: 'AI处理中',
          current_node: 'generate_polished_text',
          completed_count: 6,
          total_nodes: 7,
          progress_percent: 85.7,
          current_node_display: 'AI生成采购需求',
        },
      });
    });

    expect(getTaskGroup()?.contentMessage?.status).toBe('generating');
  });

  it('marks task-content as completed when generate_polished_text completion log arrives', async () => {
    mockGetTaskStatus.mockResolvedValue(createRunningTaskStatus());

    renderHook(() =>
      useChatSSE({
        taskId: 'task-1',
        conversationId: 'conv-1',
      })
    );

    await waitFor(() => {
      expect(latestOptions?.endpoint).toBe('/api/stream/task-1');
    });

    act(() => {
      latestOptions?.onMessage?.({
        event: 'progress',
        id: '2',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          status: 'running',
          progress_text: 'AI处理中',
          current_node: 'generate_polished_text',
          completed_count: 6,
          total_nodes: 7,
          progress_percent: 85.7,
          current_node_display: 'AI生成采购需求',
        },
      });
    });

    expect(getTaskGroup()?.contentMessage?.status).toBe('generating');

    act(() => {
      latestOptions?.onMessage?.({
        event: 'llm',
        id: '3',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          node: 'generate_polished_text',
          content: '这是最终 AI 内容',
          content_mode: 'snapshot',
          is_complete: true,
        },
      });
      latestOptions?.onMessage?.({
        event: 'log',
        id: '4',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          level: 'INFO',
          message: '[generate_polished_text] AI生成采购需求 完成 (6/7)',
        },
      });
    });

    const group = getTaskGroup();
    expect(group?.contentMessage?.status).toBe('completed');
    expect(group?.contentMessage?.content).toBe('这是最终 AI 内容');
  });

  it('replays from the beginning after refresh when only lastEventId is persisted', async () => {
    mockGetTaskStatus.mockResolvedValue(createRunningTaskStatus());
    useChatTaskSessionStore.getState().upsertSession('task-1', { lastEventId: '99' });

    renderHook(() =>
      useChatSSE({
        taskId: 'task-1',
        conversationId: 'conv-1',
      })
    );

    await waitFor(() => {
      expect(latestOptions?.endpoint).toBe('/api/stream/task-1');
      expect(latestOptions?.lastEventId).toBeNull();
    });
  });

  it('finalizes immediately from task status when runtime content is already present', async () => {
    mockGetTaskStatus.mockResolvedValue({
      task_id: 'task-1',
      status: 'completed',
      created_at: new Date().toISOString(),
      progress: createRunningTaskStatus().progress,
      result: {
        output_file: 'D:/UploadFiles/output.docx',
        file_name: 'output.docx',
        file_size: 123,
        model_used: 'deepseek',
        total_time_seconds: 12.5,
      },
    });

    useChatStreamStore.getState().replaceStream('task-1', {
      logs: [
        {
          id: 'log-1',
          timestamp: Date.now(),
          level: 'info',
          message: '日志完成',
        },
      ],
      aiText: '最终内容',
      aiComplete: false,
      lastEventId: '100',
    });

    renderHook(() =>
      useChatSSE({
        taskId: 'task-1',
        conversationId: 'conv-1',
      })
    );

    await waitFor(() => {
      const group = getTaskGroup();
      expect(group?.contentMessage?.status).toBe('completed');
    });

    const group = getTaskGroup();
    expect(group?.logMessage?.metadata?.logs).toHaveLength(1);
    expect(group?.contentMessage?.content).toBe('最终内容');
    expect(group?.downloadMessage?.metadata?.fileName).toBe('output.docx');
    expect(latestOptions?.endpoint).toBe('');
  });

  it('discards stale generating task when task status returns TASK_NOT_FOUND', async () => {
    useChatStreamStore.getState().replaceStream('task-1', {
      lastEventId: '42',
    });
    useChatTaskSessionStore.getState().upsertSession('task-1', { lastEventId: '42' });
    mockGetTaskStatus.mockRejectedValue(
      Object.assign(new Error('任务不存在'), { code: 'TASK_NOT_FOUND', status: 404 })
    );

    renderHook(() =>
      useChatSSE({
        taskId: 'task-1',
        conversationId: 'conv-1',
      })
    );

    await waitFor(() => {
      expect(useChatStore.getState().findTaskMessageGroup('task-1')).toBeNull();
    });

    expect(useChatStore.getState().hasActiveTasks()).toBe(false);
    expect(useChatTaskSessionStore.getState().sessions['task-1']).toBeUndefined();
    expect(useChatStreamStore.getState().streams['task-1']).toBeUndefined();
    expect(latestOptions?.endpoint).toBe('');
  });

  it('does not re-run task hydration when only callbacks change', async () => {
    mockGetTaskStatus.mockResolvedValue(createRunningTaskStatus());

    const firstOnComplete = jest.fn();
    const secondOnComplete = jest.fn();

    const { rerender } = renderHook(
      ({ onComplete }) =>
        useChatSSE({
          taskId: 'task-1',
          conversationId: 'conv-1',
          onComplete,
        }),
      {
        initialProps: { onComplete: firstOnComplete },
      }
    );

    await waitFor(() => {
      expect(mockGetTaskStatus).toHaveBeenCalledTimes(1);
    });

    rerender({ onComplete: secondOnComplete });

    await act(async () => {
      await Promise.resolve();
    });

    expect(mockGetTaskStatus).toHaveBeenCalledTimes(1);
  });

  it('closes the active SSE connection when a done event arrives', async () => {
    mockGetTaskStatus.mockResolvedValue(createRunningTaskStatus());

    renderHook(() =>
      useChatSSE({
        taskId: 'task-1',
        conversationId: 'conv-1',
      })
    );

    await waitFor(() => {
      expect(latestOptions?.endpoint).toBe('/api/stream/task-1');
    });

    act(() => {
      latestOptions?.onMessage?.({
        event: 'done',
        id: '4',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          success: true,
          message: '任务完成',
          output_file: 'D:/UploadFiles/output.docx',
          processing_time: 12.5,
        },
      });
    });

    expect(latestCloseMock).toHaveBeenCalledTimes(1);
  });

  it('closes the active SSE connection when a fatal error arrives', async () => {
    const onError = jest.fn();
    mockGetTaskStatus.mockResolvedValue(createRunningTaskStatus());

    renderHook(() =>
      useChatSSE({
        taskId: 'task-1',
        conversationId: 'conv-1',
        onError,
      })
    );

    await waitFor(() => {
      expect(latestOptions?.endpoint).toBe('/api/stream/task-1');
    });

    act(() => {
      latestOptions?.onMessage?.({
        event: 'error',
        id: '4',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          error: '生成失败',
          is_fatal: true,
        },
      });
    });

    expect(latestCloseMock).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith('生成失败');
  });

  it('closes the active SSE connection when a non-fatal cancel event arrives', async () => {
    const onComplete = jest.fn();
    mockGetTaskStatus.mockResolvedValue(createRunningTaskStatus());

    renderHook(() =>
      useChatSSE({
        taskId: 'task-1',
        conversationId: 'conv-1',
        onComplete,
      })
    );

    await waitFor(() => {
      expect(latestOptions?.endpoint).toBe('/api/stream/task-1');
    });

    act(() => {
      latestOptions?.onMessage?.({
        event: 'error',
        id: '4',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          error: '任务已取消',
          is_fatal: false,
        },
      });
    });

    expect(latestCloseMock).toHaveBeenCalledTimes(1);
    expect(onComplete).toHaveBeenCalledTimes(1);
  });
});
