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
    task_kind: 'generate' as const,
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

function createRewriteRunningTaskStatus() {
  return {
    task_id: 'task-1',
    task_kind: 'rewrite' as const,
    status: 'running' as const,
    created_at: new Date().toISOString(),
    progress: {
      completed_nodes: ['resolve_rewrite_target'],
      running_nodes: ['rewrite_text'],
      current_node: 'rewrite_text',
      completed_count: 1,
      total_nodes: 4,
      progress_percent: 25,
    },
  };
}

function createEditRunningTaskStatus() {
  return {
    task_id: 'task-1',
    task_kind: 'edit' as const,
    status: 'running' as const,
    created_at: new Date().toISOString(),
    progress: {
      completed_nodes: ['resolve_edit_target', 'extract_edit_context'],
      running_nodes: ['edit_text'],
      current_node: 'edit_text',
      completed_count: 2,
      total_nodes: 5,
      progress_percent: 40,
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
    conversationDrafts: {},
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
    conversationDrafts: {},
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
          style_writeback: {
            summary: '样式回填: 抽取=1, 尝试=1, 成功=1, 跳过=0, 失败=0',
            extracted: 1,
            attempted: 1,
            applied: 1,
            skipped: 0,
            failed: 0,
            applied_by_style: { strikethrough: 1 },
            skipped_by_reason: {},
          },
        },
      });
    });

    const completedGroup = getTaskGroup();
    expect(completedGroup?.logMessage?.status).toBe('completed');
    expect(completedGroup?.contentMessage?.status).toBe('completed');
    expect(completedGroup?.contentMessage?.content).toBe('你好啊');
    expect(completedGroup?.downloadMessage?.metadata?.outputFile).toBe(
      'D:/UploadFiles/output.docx'
    );
    expect(completedGroup?.downloadMessage?.metadata?.styleWriteback).toEqual({
      summary: '样式回填: 抽取=1, 尝试=1, 成功=1, 跳过=0, 失败=0',
      extracted: 1,
      attempted: 1,
      applied: 1,
      skipped: 0,
      failed: 0,
      applied_by_style: { strikethrough: 1 },
      skipped_by_reason: {},
    });
    expect(useChatStreamStore.getState().streams['task-1']).toBeUndefined();
    expect(useChatTaskSessionStore.getState().sessions['task-1']).toBeUndefined();
  });

  it('keeps node-based agent_step stream cards after done', async () => {
    mockGetTaskStatus.mockResolvedValue({
      ...createRunningTaskStatus(),
      progress: {
        ...createRunningTaskStatus().progress,
        running_nodes: ['content_agent'],
        current_node: 'content_agent',
      },
    });

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
        event: 'agent_step',
        id: '1',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'generate',
          step_type: 'stream',
          round: 0,
          node: 'content_generate_agent',
          is_complete: true,
          content: '智能体初稿正文',
          findings: [],
        },
      });
      latestOptions?.onMessage?.({
        event: 'agent_step',
        id: '2',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'generate',
          step_type: 'stream',
          round: 1,
          node: 'content_verify_agent',
          is_complete: true,
          content: '[{"evidence":"交付地点缺失","fix_hint":"补充交付地点"}]',
          findings: [
            {
              evidence: '交付地点缺失',
              fix_hint: '补充交付地点',
            },
          ],
        },
      });
      latestOptions?.onMessage?.({
        event: 'agent_step',
        id: '3',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'generate',
          step_type: 'stream',
          round: 1,
          node: 'content_revise_agent',
          is_complete: true,
          content: '第一轮 AI 修改内容',
          findings: [
            {
              evidence: '交付地点缺失',
              fix_hint: '补充交付地点',
            },
          ],
        },
      });
      latestOptions?.onMessage?.({
        event: 'agent_step',
        id: '4',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'generate',
          step_type: 'stream',
          round: 2,
          node: 'content_verify_agent',
          is_complete: true,
          content: '[{"evidence":"验收标准不明确","fix_hint":"补充验收标准"}]',
          findings: [
            {
              evidence: '验收标准不明确',
              fix_hint: '补充验收标准',
            },
          ],
        },
      });
      latestOptions?.onMessage?.({
        event: 'done',
        id: '5',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'generate',
          success: true,
          message: '任务完成',
          output_file: 'D:/UploadFiles/output.docx',
          processing_time: 12.5,
        },
      });
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    const agentMessages = conversation?.messages.filter(
      (message) => message.metadata?.messageKind === 'agent-step'
    );
    const auditMessage = agentMessages?.find(
      (message) => message.metadata?.agentStepNode === 'content_verify_agent'
    );
    const revisionMessage = agentMessages?.find(
      (message) => message.metadata?.agentStepNode === 'content_revise_agent'
    );
    const group = getTaskGroup();

    expect(agentMessages).toHaveLength(3);
    expect(agentMessages?.map((message) => message.metadata?.agentStepNode)).toEqual([
      'content_generate_agent',
      'content_verify_agent',
      'content_revise_agent',
    ]);
    expect(agentMessages?.[0].content).toBe('智能体初稿正文');
    expect(auditMessage?.content).toBe('[{"evidence":"验收标准不明确","fix_hint":"补充验收标准"}]');
    expect(auditMessage?.metadata?.agentStepAuditRounds).toHaveLength(2);
    expect(auditMessage?.metadata?.agentStepRound).toBe(2);
    expect(revisionMessage?.content).toBe('第一轮 AI 修改内容');
    expect(group?.downloadMessage?.metadata?.outputFile).toBe('D:/UploadFiles/output.docx');
    expect(group?.contentMessage).toBeUndefined();
    expect(useChatStreamStore.getState().streams['task-1']).toBeUndefined();
  });

  it('removes task-content if agent_step arrives after llm snapshot placeholder', async () => {
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
        event: 'llm',
        id: '1',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          node: 'generate_polished_text',
          content: '普通 LLM 快照',
          content_mode: 'snapshot',
          is_complete: false,
        },
      });
    });

    expect(getTaskGroup()?.contentMessage?.status).toBe('generating');

    act(() => {
      latestOptions?.onMessage?.({
        event: 'agent_step',
        id: '2',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'generate',
          step_type: 'stream',
          round: 0,
          node: 'content_generate_agent',
          is_complete: true,
          content: '智能体初稿正文',
          findings: [],
        },
      });
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    const agentMessages = conversation?.messages.filter(
      (message) => message.metadata?.messageKind === 'agent-step'
    );

    expect(getTaskGroup()?.contentMessage).toBeUndefined();
    expect(agentMessages).toHaveLength(1);
    expect(agentMessages?.[0].content).toBe('智能体初稿正文');
    expect(conversation?.messages.some((message) => message.content === '普通 LLM 快照')).toBe(
      false
    );
  });

  it('does not create task-content from llm snapshot when conversation uses agent mode', async () => {
    mockGetTaskStatus.mockResolvedValue({
      ...createRunningTaskStatus(),
      progress: {
        ...createRunningTaskStatus().progress,
        running_nodes: ['content_agent'],
        current_node: 'content_agent',
      },
    });
    useChatStore.setState((state) => ({
      ...state,
      conversationDrafts: {
        ...state.conversationDrafts,
        'conv-1': {
          generation_mode: 'agent',
        },
      },
    }));

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
        event: 'llm',
        id: '1',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          node: 'generate_polished_text',
          content: '普通 LLM 快照',
          content_mode: 'snapshot',
          is_complete: false,
        },
      });
    });

    expect(useChatStreamStore.getState().streams['task-1']?.aiText).toBe('普通 LLM 快照');
    expect(getTaskGroup()?.contentMessage).toBeUndefined();
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

    mockGetTaskStatus.mockResolvedValue(createRunningTaskStatus());
    rerender({ status: 'running' as const });

    await waitFor(() => {
      expect(mockGetTaskStatus).toHaveBeenCalledWith('task-1');
      expect(latestOptions?.endpoint).toBe('/api/stream/task-1');
    });
    expect(getTaskGroup()?.logMessage?.metadata?.messageKind).toBe('task-log');
  });

  it('clears queued cancelled task without creating any chat cards', async () => {
    setQueueOnlyTaskState();
    mockGetTaskStatus.mockResolvedValue({
      task_id: 'task-1',
      task_kind: 'generate',
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
      task_kind: 'generate',
      status: 'completed',
      created_at: new Date().toISOString(),
      progress: createRunningTaskStatus().progress,
      result: {
        output_file: 'D:/UploadFiles/output.docx',
        file_name: 'output.docx',
        file_size: 123,
        model_used: 'deepseek',
        total_time_seconds: 12.5,
        style_writeback: {
          summary: '样式回填: 抽取=2, 尝试=2, 成功=1, 跳过=1, 失败=0',
          extracted: 2,
          attempted: 2,
          applied: 1,
          skipped: 1,
          failed: 0,
          applied_by_style: { bold: 1 },
          skipped_by_reason: { low_confidence: 1 },
        },
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
    expect(group?.downloadMessage?.metadata?.styleWriteback).toEqual({
      summary: '样式回填: 抽取=2, 尝试=2, 成功=1, 跳过=1, 失败=0',
      extracted: 2,
      attempted: 2,
      applied: 1,
      skipped: 1,
      failed: 0,
      applied_by_style: { bold: 1 },
      skipped_by_reason: { low_confidence: 1 },
    });
    expect(latestOptions?.endpoint).toBe('');
  });

  it('marks stale generating task as interrupted when task status returns TASK_NOT_FOUND', async () => {
    useChatStreamStore.getState().replaceStream('task-1', {
      logs: [
        {
          id: 'log-stream',
          timestamp: Date.now(),
          level: 'info',
          message: '正在执行',
        },
      ],
      aiText: '已生成一半的内容',
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
      const group = useChatStore.getState().findTaskMessageGroup('task-1');
      expect(group?.logMessage?.status).toBe('error');
      expect(group?.contentMessage?.status).toBe('error');
    });

    const group = useChatStore.getState().findTaskMessageGroup('task-1');
    expect(group?.logMessage?.metadata?.localTaskReason).toBe('backend_restart');
    expect(group?.logMessage?.metadata?.logs).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ message: '正在执行' }),
        expect.objectContaining({ message: '服务已重启，任务已中断，可重试' }),
      ])
    );
    expect(group?.contentMessage?.content).toBe('已生成一半的内容');
    expect(group?.contentMessage?.error).toBe('服务已重启，任务已中断，可重试');
    expect(useChatStore.getState().hasActiveTasks()).toBe(false);
    expect(useChatStore.getState().getCurrentConversation()?.currentTaskId).toBeUndefined();
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

  it('keeps agent-step cards without task-content when a fatal agent error arrives', async () => {
    const onError = jest.fn();
    mockGetTaskStatus.mockResolvedValue({
      ...createRunningTaskStatus(),
      progress: {
        ...createRunningTaskStatus().progress,
        running_nodes: ['content_agent'],
        current_node: 'content_agent',
      },
    });

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
        event: 'agent_step',
        id: '1',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'generate',
          step_type: 'stream',
          round: 0,
          node: 'content_generate_agent',
          is_complete: true,
          content: '智能体初稿正文',
          findings: [],
        },
      });
      useChatStreamStore.getState().setAIContent('task-1', '不应出现的普通 AI 内容卡', true);
      latestOptions?.onMessage?.({
        event: 'error',
        id: '2',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'generate',
          error: 'Request timed out.',
          is_fatal: true,
        },
      });
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    const agentMessages = conversation?.messages.filter(
      (message) => message.metadata?.messageKind === 'agent-step'
    );
    const group = getTaskGroup();

    expect(latestCloseMock).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith('Request timed out.');
    expect(agentMessages).toHaveLength(1);
    expect(agentMessages?.[0].content).toBe('智能体初稿正文');
    expect(group?.logMessage?.status).toBe('error');
    expect(group?.logMessage?.metadata?.logs).toEqual(
      expect.arrayContaining([expect.objectContaining({ message: 'Request timed out.' })])
    );
    expect(group?.contentMessage).toBeUndefined();
    expect(
      conversation?.messages.some((message) => message.content === '不应出现的普通 AI 内容卡')
    ).toBe(false);
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

  it('ignores late SSE events after a task is locally cancelled', async () => {
    mockGetTaskStatus.mockResolvedValue(createRunningTaskStatus());

    useChatStreamStore.getState().replaceStream('task-1', {
      logs: [
        {
          id: 'log-stream',
          timestamp: Date.now(),
          level: 'info',
          message: '正在修改',
        },
      ],
      aiText: '部分修改内容',
      aiComplete: false,
      lastEventId: '10',
    });
    useChatTaskSessionStore.getState().upsertSession('task-1', { lastEventId: '10' });

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
      useChatStore.getState().cancelTask('task-1', {
        logs: [
          {
            id: 'log-stream',
            timestamp: Date.now(),
            level: 'info',
            message: '正在修改',
          },
        ],
        aiText: '部分修改内容',
      });
      useChatStreamStore.getState().clearStream('task-1');
      useChatTaskSessionStore.getState().removeSession('task-1');
    });

    expect(getTaskGroup()?.logMessage?.status).toBe('cancelled');

    act(() => {
      latestOptions?.onMessage?.({
        event: 'log',
        id: '11',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          level: 'INFO',
          message: '[delete_tender_param] 开始修复',
          node: 'delete_tender_param',
        },
      });
    });

    const group = getTaskGroup();
    expect(group?.logMessage?.status).toBe('cancelled');
    expect(useChatStreamStore.getState().streams['task-1']).toBeUndefined();
    expect(useChatTaskSessionStore.getState().sessions['task-1']).toBeUndefined();
  });

  it('treats rewrite_text as the AI content trigger for rewrite tasks', async () => {
    useChatStore.setState((state) => ({
      ...state,
      taskSummaries: {
        'task-1': {
          task_id: 'task-1',
          task_kind: 'rewrite',
          status: 'running',
          updated_at: Date.now(),
        },
      },
    }));
    mockGetTaskStatus.mockResolvedValue(createRewriteRunningTaskStatus());

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
        id: '1',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'rewrite',
          status: 'running',
          progress_text: '1/4',
          current_node: 'rewrite_text',
          completed_count: 1,
          total_nodes: 4,
          progress_percent: 25,
          current_node_display: 'AI重写内容',
        },
      });
      latestOptions?.onMessage?.({
        event: 'llm',
        id: '2',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          node: 'rewrite_text',
          content: '修改后的内容',
          content_mode: 'snapshot',
          is_complete: true,
        },
      });
      latestOptions?.onMessage?.({
        event: 'done',
        id: '3',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'rewrite',
          success: true,
          message: '修改任务完成',
          output_file: 'D:/UploadFiles/output-rewrite.docx',
          processing_time: 3.2,
        },
      });
    });

    const group = getTaskGroup();
    expect(group?.contentMessage?.status).toBe('completed');
    expect(group?.contentMessage?.content).toBe('修改后的内容');
    expect(group?.contentMessage?.metadata?.taskKind).toBe('rewrite');
    expect(group?.downloadMessage?.metadata?.taskKind).toBe('rewrite');
  });

  it('treats edit_text as the AI content trigger for edit tasks', async () => {
    useChatStore.setState((state) => ({
      ...state,
      taskSummaries: {
        'task-1': {
          task_id: 'task-1',
          task_kind: 'edit',
          status: 'running',
          updated_at: Date.now(),
        },
      },
    }));
    mockGetTaskStatus.mockResolvedValue(createEditRunningTaskStatus());

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
        id: '1',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'edit',
          status: 'running',
          progress_text: '2/5',
          current_node: 'edit_text',
          completed_count: 2,
          total_nodes: 5,
          progress_percent: 40,
          current_node_display: 'AI生成修改正文',
        },
      });
      latestOptions?.onMessage?.({
        event: 'llm',
        id: '2',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          node: 'edit_text',
          content: '更新后的正文',
          content_mode: 'snapshot',
          is_complete: true,
        },
      });
      latestOptions?.onMessage?.({
        event: 'done',
        id: '3',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'edit',
          success: true,
          message: '文档修改完成',
          output_file: 'D:/UploadFiles/output-edit.docx',
          processing_time: 2.6,
        },
      });
    });

    const group = getTaskGroup();
    expect(group?.contentMessage?.status).toBe('completed');
    expect(group?.contentMessage?.content).toBe('更新后的正文');
    expect(group?.contentMessage?.metadata?.taskKind).toBe('edit');
    expect(group?.downloadMessage?.metadata?.taskKind).toBe('edit');
  });

  it('keeps the final multiline edit snapshot through completion logs and done', async () => {
    useChatStore.setState((state) => ({
      ...state,
      taskSummaries: {
        'task-1': {
          task_id: 'task-1',
          task_kind: 'edit',
          status: 'running',
          updated_at: Date.now(),
        },
      },
    }));
    mockGetTaskStatus.mockResolvedValue(createEditRunningTaskStatus());

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
        id: '1',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'edit',
          status: 'running',
          progress_text: '2/5',
          current_node: 'edit_text',
          completed_count: 2,
          total_nodes: 5,
          progress_percent: 40,
          current_node_display: 'AI生成修改正文',
        },
      });
      latestOptions?.onMessage?.({
        event: 'llm',
        id: '2',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          node: 'edit_text',
          content: '单行草稿',
          content_mode: 'snapshot',
          is_complete: false,
        },
      });
      latestOptions?.onMessage?.({
        event: 'log',
        id: '3',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          level: 'INFO',
          message: '[edit_text] AI生成修改正文 完成 (4/5)',
          node: 'edit_text',
        },
      });
    });

    expect(getTaskGroup()?.contentMessage?.status).toBe('generating');

    act(() => {
      latestOptions?.onMessage?.({
        event: 'llm',
        id: '4',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          node: 'edit_text',
          content: '第一段\r\n第二段\r第三段',
          content_mode: 'snapshot',
          is_complete: true,
        },
      });
    });

    expect(useChatStreamStore.getState().streams['task-1']?.aiText).toBe('第一段\n第二段\n第三段');
    expect(getTaskGroup()?.contentMessage?.status).toBe('completed');
    expect(getTaskGroup()?.contentMessage?.content).toBe('第一段\n第二段\n第三段');

    act(() => {
      latestOptions?.onMessage?.({
        event: 'done',
        id: '5',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'edit',
          success: true,
          message: '文档修改完成',
          output_file: 'D:/UploadFiles/output-edit.docx',
          processing_time: 2.6,
        },
      });
    });

    const group = getTaskGroup();
    expect(group?.contentMessage?.status).toBe('completed');
    expect(group?.contentMessage?.content).toBe('第一段\n第二段\n第三段');
    expect(useChatStreamStore.getState().streams['task-1']).toBeUndefined();
  });
});
