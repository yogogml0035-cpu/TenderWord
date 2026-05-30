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

function createCommentSupplementRunningTaskStatus() {
  return {
    task_id: 'task-1',
    task_kind: 'comment_supplement' as const,
    status: 'running' as const,
    created_at: new Date().toISOString(),
    progress: {
      completed_nodes: ['prepare_comment_supplement'],
      running_nodes: ['comment_agent'],
      current_node: 'comment_agent',
      completed_count: 1,
      total_nodes: 4,
      progress_percent: 25,
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
          task_kind: 'generate',
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
          comment_writeback: {
            summary: 'AI 批注写入: 生成=3, 成功=1, 跳过=0, 失败=2',
            generated: 3,
            added: 1,
            failed: 2,
            skipped: 0,
            warning: true,
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
    expect(completedGroup?.downloadMessage?.metadata?.commentWriteback).toEqual({
      summary: 'AI 批注写入: 生成=3, 成功=1, 跳过=0, 失败=2',
      generated: 3,
      added: 1,
      failed: 2,
      skipped: 0,
      warning: true,
    });
    expect(useChatStreamStore.getState().streams['task-1']).toBeUndefined();
    expect(useChatTaskSessionStore.getState().sessions['task-1']).toBeUndefined();
  });

  it('keeps legacy node-based agent_step stream cards after done', async () => {
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
          round: 1,
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
    const firstAuditMessage = agentMessages?.find(
      (message) =>
        message.metadata?.agentStepNode === 'content_verify_agent' &&
        message.metadata?.agentStepRound === 1
    );
    const secondAuditMessage = agentMessages?.find(
      (message) =>
        message.metadata?.agentStepNode === 'content_verify_agent' &&
        message.metadata?.agentStepRound === 2
    );
    const revisionMessage = agentMessages?.find(
      (message) => message.metadata?.agentStepNode === 'content_revise_agent'
    );
    const group = getTaskGroup();

    expect(agentMessages).toHaveLength(4);
    expect(agentMessages?.map((message) => message.metadata?.agentStepNode)).toEqual([
      'content_generate_agent',
      'content_verify_agent',
      'content_revise_agent',
      'content_verify_agent',
    ]);
    expect(agentMessages?.[0].content).toBe('智能体初稿正文');
    expect(firstAuditMessage?.content).toBe('[{"evidence":"交付地点缺失","fix_hint":"补充交付地点"}]');
    expect(firstAuditMessage?.metadata?.agentStepAuditRounds).toHaveLength(1);
    expect(firstAuditMessage?.metadata?.agentStepRound).toBe(1);
    expect(revisionMessage?.content).toBe('第一轮 AI 修改内容');
    expect(secondAuditMessage?.content).toBe('[{"evidence":"验收标准不明确","fix_hint":"补充验收标准"}]');
    expect(secondAuditMessage?.metadata?.agentStepAuditRounds).toHaveLength(1);
    expect(secondAuditMessage?.metadata?.agentStepRound).toBe(2);
    expect(group?.downloadMessage?.metadata?.outputFile).toBe('D:/UploadFiles/output.docx');
    expect(group?.contentMessage).toBeUndefined();
    expect(useChatStreamStore.getState().streams['task-1']).toBeUndefined();
  });

  it('aggregates structured content_agent agent_step events into one card', async () => {
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

    const draftRound = {
      round: 1,
      phase: 'draft' as const,
      label: '初稿生成',
      summary: '初稿生成完成，约 4 字。',
      issue_count: 0,
      fix_count: 0,
      content: '初稿正文',
      findings: [],
    };
    const auditRound = {
      round: 1,
      phase: 'audit' as const,
      label: '第 1 轮审核发现',
      summary: '第 1 轮审核发现 1 个问题。',
      issue_count: 1,
      fix_count: 0,
      content: '[{"evidence":"缺少交付地点","fix_hint":"补充交付地点"}]',
      findings: [
        {
          evidence: '缺少交付地点',
          fix_hint: '补充交付地点',
        },
      ],
    };
    const revisionRound = {
      round: 1,
      phase: 'revision' as const,
      label: '第 1 轮修复',
      summary: '第 1 轮修复完成，已处理 1 个问题。',
      issue_count: 1,
      fix_count: 1,
      content: '修复正文',
      findings: auditRound.findings,
    };

    act(() => {
      latestOptions?.onMessage?.({
        event: 'agent_step',
        id: '1',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'generate',
          step_type: 'stream',
          round: 1,
          node: 'content_generate_agent',
          is_complete: false,
          content: '初稿正文',
          findings: [],
          content_agent: {
            phase: 'draft',
            summary: '初稿生成完成，约 4 字。',
            rounds: [draftRound],
            highlights: [],
          },
        },
      });
    });

    let conversation = useChatStore.getState().getCurrentConversation();
    let agentMessages = conversation?.messages.filter(
      (message) => message.metadata?.messageKind === 'agent-step'
    );
    expect(agentMessages).toHaveLength(1);
    expect(agentMessages?.[0].metadata?.agentStepNode).toBe('content_agent');
    expect(agentMessages?.[0].metadata?.contentAgent?.phase).toBe('draft');
    expect(useChatStreamStore.getState().streams['task-1']?.agentSteps?.['content_agent']).toMatchObject({
      content: '初稿正文',
      contentAgent: expect.objectContaining({ phase: 'draft' }),
      isComplete: false,
    });

    act(() => {
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
          content: '[{"evidence":"缺少交付地点","fix_hint":"补充交付地点"}]',
          findings: auditRound.findings,
          content_agent: {
            phase: 'audit',
            summary: '第 1 轮审核发现 1 个问题。',
            rounds: [draftRound, auditRound],
            highlights: auditRound.findings,
          },
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
          content: '修复正文',
          findings: auditRound.findings,
          content_agent: {
            phase: 'revision',
            summary: '第 1 轮修复完成，已处理 1 个问题。',
            rounds: [draftRound, auditRound, revisionRound],
            highlights: auditRound.findings,
          },
        },
      });
      latestOptions?.onMessage?.({
        event: 'agent_step',
        id: '4',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'generate',
          step_type: 'final',
          round: 2,
          node: 'content_agent',
          is_complete: true,
          content: '最终完成，修复 1 轮，最终正文约 4 字。',
          findings: [],
          content_agent: {
            phase: 'final',
            summary: '最终完成，修复 1 轮，最终正文约 4 字。',
            rounds: [draftRound, auditRound, revisionRound],
            highlights: [],
            final_result: {
              summary: '最终完成，修复 1 轮，最终正文约 4 字。',
              revision_rounds: 1,
              final_chars: 4,
              issue_count: 0,
              content: '最终正文',
            },
          },
        },
      });
    });

    conversation = useChatStore.getState().getCurrentConversation();
    agentMessages = conversation?.messages.filter(
      (message) => message.metadata?.messageKind === 'agent-step'
    );

    expect(agentMessages).toHaveLength(1);
    expect(agentMessages?.[0].metadata?.agentStepKey).toBe('content_agent');
    expect(agentMessages?.[0].metadata?.contentAgent?.phase).toBe('final');
    expect(agentMessages?.[0].metadata?.contentAgent?.rounds).toHaveLength(3);
    expect(agentMessages?.[0].content).toBe('最终正文');
    expect(agentMessages?.[0].status).toBe('completed');
  });

  it('keeps comment_agent incomplete snapshots transient and persists final snapshot', async () => {
    mockGetTaskStatus.mockResolvedValue({
      ...createRunningTaskStatus(),
      progress: {
        ...createRunningTaskStatus().progress,
        running_nodes: ['comment_agent'],
        current_node: 'comment_agent',
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
        event: 'agent_step',
        id: '1',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'generate',
          step_type: 'tool_snapshot',
          round: 1,
          node: 'comment_agent',
          is_complete: false,
          content: '工具轮次 1：批注锚点校验快照',
          findings: [],
          comment_agent: {
            phase: 'validation_round',
            rounds: [
              {
                round: 1,
                label: '第 1 轮锚点校验',
                passed: 0,
                failed: 1,
                skipped: 0,
                highlights: [
                  {
                    index: 1,
                    status: '需修复',
                    reason: '当前锚点未在最终正文中精确匹配',
                    original_reference_text: '★7.投标人须提供售后服务承诺',
                    reference_text: '★7.投标人须提供售后服务承诺',
                    candidate_fragments: ['7.投标人须提供售后服务承诺'],
                  },
                ],
              },
            ],
            highlights: [],
          },
        },
      });
      latestOptions?.onMessage?.({
        event: 'agent_step',
        id: '2',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'generate',
          step_type: 'tool_snapshot',
          round: 1,
          node: 'comment_agent',
          is_complete: false,
          content: '工具轮次 2：批注锚点校验快照',
          findings: [],
          comment_agent: {
            phase: 'validation_round',
            rounds: [
              {
                round: 1,
                label: '第 1 轮锚点校验',
                passed: 0,
                failed: 1,
                skipped: 0,
                highlights: [],
              },
              {
                round: 2,
                label: '第 2 轮修复复核',
                passed: 1,
                failed: 0,
                skipped: 0,
                highlights: [
                  {
                    index: 1,
                    status: '已修复',
                    reason: '锚点已通过校验',
                    original_reference_text: '★7.投标人须提供售后服务承诺',
                    reference_text: '7.投标人须提供售后服务承诺',
                    candidate_fragments: [],
                  },
                ],
              },
            ],
            highlights: [],
          },
        },
      });
    });

    let conversation = useChatStore.getState().getCurrentConversation();
    let commentAgentMessage = conversation?.messages.find(
      (message) => message.metadata?.agentStepNode === 'comment_agent'
    );

    expect(commentAgentMessage?.content).toBe('');
    expect(commentAgentMessage?.status).toBe('generating');
    expect(useChatStreamStore.getState().streams['task-1']?.agentSteps).toEqual({
      'comment_agent:1': {
        content: '工具轮次 2：批注锚点校验快照',
        commentAgent: expect.objectContaining({
          phase: 'validation_round',
          rounds: expect.arrayContaining([
            expect.objectContaining({ label: '第 2 轮修复复核' }),
          ]),
        }),
        isComplete: false,
      },
    });

    act(() => {
      latestOptions?.onMessage?.({
        event: 'agent_step',
        id: '3',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'generate',
          step_type: 'final',
          round: 1,
          node: 'comment_agent',
          is_complete: true,
          content: 'comment_agent 最终写入统计',
          findings: [],
          comment_agent: {
            phase: 'final',
            rounds: [
              {
                round: 1,
                label: '第 1 轮锚点校验',
                passed: 0,
                failed: 1,
                skipped: 0,
                highlights: [],
              },
              {
                round: 2,
                label: '第 2 轮修复复核',
                passed: 1,
                failed: 0,
                skipped: 0,
                highlights: [],
              },
            ],
            highlights: [],
            final_validation: {
              round: 0,
              label: '最终静默复校验',
              passed: 1,
              failed: 0,
              skipped: 0,
              highlights: [],
            },
            writeback: {
              attempted: 1,
              added: 1,
              failed: 0,
              skipped: 0,
              issues: [],
            },
          },
        },
      });
    });

    conversation = useChatStore.getState().getCurrentConversation();
    commentAgentMessage = conversation?.messages.find(
      (message) => message.metadata?.agentStepNode === 'comment_agent'
    );

    expect(commentAgentMessage?.content).toBe('comment_agent 最终写入统计');
    expect(commentAgentMessage?.status).toBe('completed');
    expect(commentAgentMessage?.metadata?.commentAgent?.rounds).toHaveLength(2);
    expect(commentAgentMessage?.metadata?.commentAgent?.writeback?.added).toBe(1);
  });

  it('shows comment_agent card for comment_supplement tasks and keeps one download card', async () => {
    mockGetTaskStatus.mockResolvedValue(createCommentSupplementRunningTaskStatus());

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
          task_kind: 'comment_supplement',
          step_type: 'tool_snapshot',
          round: 1,
          node: 'comment_agent',
          is_complete: false,
          content: '工具轮次 1：批注锚点校验快照',
          findings: [],
        },
      });
      latestOptions?.onMessage?.({
        event: 'agent_step',
        id: '2',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'comment_supplement',
          step_type: 'final',
          round: 1,
          node: 'comment_agent',
          is_complete: true,
          content: 'comment_agent 最终写入统计',
          findings: [],
        },
      });
      latestOptions?.onMessage?.({
        event: 'done',
        id: '3',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'comment_supplement',
          success: true,
          message: '任务完成',
          output_file: 'D:/UploadFiles/commented.docx',
          file_name: 'commented.docx',
          processing_time: 12.5,
        },
      });
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    const agentMessages = conversation?.messages.filter(
      (message) => message.metadata?.messageKind === 'agent-step'
    );
    const group = getTaskGroup();

    expect(agentMessages).toHaveLength(1);
    expect(agentMessages?.[0].metadata?.agentStepNode).toBe('comment_agent');
    expect(agentMessages?.[0].metadata?.taskKind).toBe('comment_supplement');
    expect(agentMessages?.[0].content).toBe('comment_agent 最终写入统计');
    expect(agentMessages?.[0].status).toBe('completed');
    expect(group?.contentMessage).toBeUndefined();
    expect(group?.downloadMessage?.metadata?.taskKind).toBe('comment_supplement');
    expect(group?.downloadMessage?.metadata?.outputFile).toBe('D:/UploadFiles/commented.docx');
  });

  it('ignores comment_agent agent_step events for workflow generate tasks', async () => {
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
        event: 'agent_step',
        id: '1',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'generate',
          step_type: 'stream',
          round: 1,
          node: 'comment_agent',
          is_complete: false,
          content: 'workflow 不应展示的批注智能体内容',
          findings: [],
        },
      });
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    expect(
      conversation?.messages.some((message) => message.metadata?.agentStepNode === 'comment_agent')
    ).toBe(false);
  });

  it('keeps empty running verify agent-step compact until final [] arrives', async () => {
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
        event: 'agent_step',
        id: '1',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'generate',
          step_type: 'stream',
          round: 1,
          node: 'content_verify_agent',
          is_complete: false,
          content: '',
          findings: [],
        },
      });
    });

    let conversation = useChatStore.getState().getCurrentConversation();
    let verifyMessage = conversation?.messages.find(
      (message) => message.metadata?.agentStepNode === 'content_verify_agent'
    );

    expect(verifyMessage?.content).toBe('');
    expect(verifyMessage?.status).toBe('generating');

    act(() => {
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
          content: '[]',
          findings: [],
        },
      });
    });

    conversation = useChatStore.getState().getCurrentConversation();
    verifyMessage = conversation?.messages.find(
      (message) => message.metadata?.agentStepNode === 'content_verify_agent'
    );

    expect(verifyMessage?.content).toBe('[]');
    expect(verifyMessage?.status).toBe('completed');
  });

  it('buffers incomplete agent_step snapshots outside the persisted chat store', async () => {
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
          round: 1,
          node: 'content_generate_agent',
          is_complete: false,
          content: '第一段',
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
          node: 'content_generate_agent',
          is_complete: false,
          content: '第一段\n第二段',
          findings: [],
        },
      });
    });

    let conversation = useChatStore.getState().getCurrentConversation();
    let agentMessage = conversation?.messages.find(
      (message) => message.metadata?.agentStepNode === 'content_generate_agent'
    );
    expect(agentMessage?.content).toBe('');
    expect(agentMessage?.status).toBe('generating');
    expect(useChatStreamStore.getState().streams['task-1']?.agentSteps).toEqual({
      'content_generate_agent:1': {
        content: '第一段\n第二段',
        isComplete: false,
      },
    });

    act(() => {
      latestOptions?.onMessage?.({
        event: 'agent_step',
        id: '3',
        data: {
          timestamp: new Date().toISOString(),
          task_id: 'task-1',
          task_kind: 'generate',
          step_type: 'stream',
          round: 1,
          node: 'content_generate_agent',
          is_complete: true,
          content: '第一段\n第二段',
          findings: [],
        },
      });
    });

    conversation = useChatStore.getState().getCurrentConversation();
    agentMessage = conversation?.messages.find(
      (message) => message.metadata?.agentStepNode === 'content_generate_agent'
    );
    expect(agentMessage?.content).toBe('第一段\n第二段');
    expect(agentMessage?.status).toBe('completed');
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
          round: 1,
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
        comment_writeback: {
          summary: 'AI 批注写入: 生成=2, 成功=2, 跳过=0, 失败=0',
          generated: 2,
          added: 2,
          failed: 0,
          skipped: 0,
          warning: false,
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
    expect(group?.downloadMessage?.metadata?.commentWriteback).toEqual({
      summary: 'AI 批注写入: 生成=2, 成功=2, 跳过=0, 失败=0',
      generated: 2,
      added: 2,
      failed: 0,
      skipped: 0,
      warning: false,
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
          round: 1,
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
