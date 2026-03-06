import { act, renderHook, waitFor } from '@testing-library/react';
import { createEmptyDualColumnContent } from '@/lib/chat-utils';
import { useChatSSE } from '@/hooks/useChatSSE';
import { useSSE } from '@/hooks/useSSE';
import { getTaskStatus } from '@/lib/api';
import { isDualColumnContent } from '@/types/chat';
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
        messages: [
          {
            id: 'msg-1',
            conversationId: 'conv-1',
            type: 'ai',
            content: createEmptyDualColumnContent(),
            timestamp: 1,
            status: 'generating',
            taskId: 'task-1',
          },
        ],
      },
    ],
    currentConversationId: 'conv-1',
    activeTaskIds: ['task-1'],
    taskMessageMap: { 'task-1': 'msg-1' },
    isLoading: false,
    error: null,
    concurrentTaskWarning: false,
    selectedTenderType: 'xjcg',
  }));

  useChatStreamStore.setState({ streams: {} });
  useChatTaskSessionStore.setState({ sessions: {} });
}

describe('useChatSSE', () => {
  let latestOptions: MockSSEOptions | null;

  beforeEach(() => {
    resetStores();
    latestOptions = null;
    mockUseSSE.mockImplementation((options) => {
      latestOptions = options;
      return {
        isConnected: true,
        isReconnecting: false,
        reconnectAttempts: 0,
        error: null,
        close: jest.fn(),
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
        messageId: 'msg-1',
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
          content: '你好啊',
          content_mode: 'snapshot',
          is_complete: false,
        },
      });
    });

    expect(useChatStreamStore.getState().streams['task-1']?.content.aiContent.text).toBe('你好啊');

    const generatingMessage = useChatStore.getState().findMessageByTaskId('task-1')?.message;
    expect(generatingMessage?.status).toBe('generating');
    expect(isDualColumnContent(generatingMessage?.content) ? generatingMessage.content.aiContent.text : '').toBe(
      ''
    );

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

    const completedMessage = useChatStore.getState().findMessageByTaskId('task-1')?.message;
    expect(completedMessage?.status).toBe('completed');
    expect(isDualColumnContent(completedMessage?.content) ? completedMessage.content.aiContent.text : '').toBe(
      '你好啊'
    );
    expect(useChatStreamStore.getState().streams['task-1']).toBeUndefined();
    expect(useChatTaskSessionStore.getState().sessions['task-1']).toBeUndefined();
  });

  it('replays from the beginning after refresh when only lastEventId is persisted', async () => {
    mockGetTaskStatus.mockResolvedValue(createRunningTaskStatus());
    useChatTaskSessionStore.getState().upsertSession('task-1', { lastEventId: '99' });

    renderHook(() =>
      useChatSSE({
        taskId: 'task-1',
        conversationId: 'conv-1',
        messageId: 'msg-1',
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
      content: {
        ...createEmptyDualColumnContent(),
        aiContent: {
          text: '最终内容',
          timestamp: Date.now(),
          isComplete: false,
        },
      },
      lastEventId: '100',
    });

    renderHook(() =>
      useChatSSE({
        taskId: 'task-1',
        conversationId: 'conv-1',
        messageId: 'msg-1',
      })
    );

    await waitFor(() => {
      const message = useChatStore.getState().findMessageByTaskId('task-1')?.message;
      expect(message?.status).toBe('completed');
    });

    const message = useChatStore.getState().findMessageByTaskId('task-1')?.message;
    expect(isDualColumnContent(message?.content) ? message.content.aiContent.text : '').toBe(
      '最终内容'
    );
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
        messageId: 'msg-1',
      })
    );

    await waitFor(() => {
      expect(useChatStore.getState().findMessageByTaskId('task-1')).toBeNull();
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
          messageId: 'msg-1',
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
});
