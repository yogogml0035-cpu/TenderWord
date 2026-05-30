import { act } from '@testing-library/react';
import { useChatStore } from '@/stores/chatStore';
import { useChatStreamStore } from '@/stores/chatStreamStore';
import { useChatTaskSessionStore } from '@/stores/chatTaskSessionStore';

function resetStore() {
  window.localStorage.clear();
  window.sessionStorage.clear();

  useChatStore.setState({
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
    activeTaskIds: [],
    taskMessageMap: {},
    conversationDrafts: {},
    taskSummaries: {},
    isLoading: false,
    error: null,
    selectedTenderType: 'xjcg',
  });
}

describe('chatStore task message grouping', () => {
  beforeEach(() => {
    resetStore();
  });

  it('startTask only binds task ownership without creating messages', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-1');
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    expect(conversation?.currentTaskId).toBe('task-1');
    expect(conversation?.messages).toHaveLength(0);
    expect(useChatStore.getState().activeTaskIds).toContain('task-1');
  });

  it('ensureTaskLogMessage lazily creates task-log message when task starts running', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-1');
      useChatStore.getState().ensureTaskLogMessage('task-1');
    });

    const group = useChatStore.getState().findTaskMessageGroup('task-1');
    expect(group?.logMessage?.status).toBe('generating');
    expect(group?.logMessage?.metadata?.messageKind).toBe('task-log');
  });

  it('reuses the rewrite placeholder bubble as the task-log message when the task starts', () => {
    let placeholderMessageId = '';

    act(() => {
      placeholderMessageId = useChatStore.getState().addMessage('conv-1', {
        type: 'ai',
        content: '正在创建修改重写任务',
        status: 'completed',
        metadata: {
          chatKind: 'rewrite',
        },
      });
      useChatStore.getState().startTask(
        'conv-1',
        'task-1',
        {
          task_kind: 'rewrite',
          status: 'queued',
        },
        {
          logMessageId: placeholderMessageId,
        }
      );
      useChatStore.getState().ensureTaskLogMessage('task-1', { status: 'generating' });
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    const group = useChatStore.getState().findTaskMessageGroup('task-1');

    expect(conversation?.messages).toHaveLength(1);
    expect(group?.logMessage?.id).toBe(placeholderMessageId);
    expect(group?.logMessage?.taskId).toBe('task-1');
    expect(group?.logMessage?.status).toBe('generating');
    expect(group?.logMessage?.content).toBe('');
    expect(group?.logMessage?.metadata?.messageKind).toBe('task-log');
    expect(group?.logMessage?.metadata?.taskKind).toBe('rewrite');
  });

  it('reuses the generate placeholder bubble as the task-log message when the task starts', () => {
    let placeholderMessageId = '';

    act(() => {
      placeholderMessageId = useChatStore.getState().addMessage('conv-1', {
        type: 'ai',
        content: '正在创建生成招标文件任务',
        status: 'completed',
        metadata: {
          chatKind: 'task-notice',
        },
      });
      useChatStore.getState().startTask(
        'conv-1',
        'task-1',
        {
          task_kind: 'generate',
          status: 'queued',
        },
        {
          logMessageId: placeholderMessageId,
        }
      );
      useChatStore.getState().ensureTaskLogMessage('task-1', { status: 'generating' });
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    const group = useChatStore.getState().findTaskMessageGroup('task-1');

    expect(conversation?.messages).toHaveLength(1);
    expect(group?.logMessage?.id).toBe(placeholderMessageId);
    expect(group?.logMessage?.taskId).toBe('task-1');
    expect(group?.logMessage?.status).toBe('generating');
    expect(group?.logMessage?.content).toBe('');
    expect(group?.logMessage?.metadata?.messageKind).toBe('task-log');
    expect(group?.logMessage?.metadata?.taskKind).toBe('generate');
  });

  it('ensureTaskContentMessage lazily creates task-content message', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-1');
      useChatStore.getState().ensureTaskLogMessage('task-1');
      useChatStore.getState().ensureTaskContentMessage('task-1');
    });

    const group = useChatStore.getState().findTaskMessageGroup('task-1');
    expect(group?.logMessage?.status).toBe('generating');
    expect(group?.contentMessage?.status).toBe('generating');
    expect(group?.contentMessage?.metadata?.messageKind).toBe('task-content');
  });

  it('markTaskContentReady sets task-content message status to completed', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-1');
      useChatStore.getState().ensureTaskLogMessage('task-1');
      useChatStore.getState().ensureTaskContentMessage('task-1');
      useChatStore.getState().markTaskContentReady('task-1', '节点完成内容');
    });

    const group = useChatStore.getState().findTaskMessageGroup('task-1');
    expect(group?.contentMessage?.status).toBe('completed');
    expect(group?.contentMessage?.content).toBe('节点完成内容');
  });

  it('upserts agent-step cards by node and round and keeps verify JSON raw', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-1', {
        task_kind: 'generate',
        status: 'running',
      });
      useChatStore.getState().upsertAgentStepMessage('task-1', {
        timestamp: new Date().toISOString(),
        task_id: 'task-1',
        task_kind: 'generate',
        step_type: 'stream',
        round: 1,
        node: 'content_generate_agent',
        is_complete: true,
        content: '智能体初稿',
        findings: [],
      });
      useChatStore.getState().upsertAgentStepMessage('task-1', {
        timestamp: new Date().toISOString(),
        task_id: 'task-1',
        task_kind: 'generate',
        step_type: 'stream',
        round: 1,
        node: 'content_verify_agent',
        is_complete: true,
        content: '[{"evidence":"缺少供货范围","fix_hint":"补充供货范围说明"}]',
        findings: [
          {
            evidence: '缺少供货范围',
            fix_hint: '补充供货范围说明',
          },
        ],
      });
      useChatStore.getState().upsertAgentStepMessage('task-1', {
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
            evidence: '缺少供货范围',
            fix_hint: '补充供货范围说明',
          },
        ],
      });
      useChatStore.getState().upsertAgentStepMessage('task-1', {
        timestamp: new Date().toISOString(),
        task_id: 'task-1',
        task_kind: 'generate',
        step_type: 'stream',
        round: 2,
        node: 'content_verify_agent',
        is_complete: true,
        content: '[{"evidence":"质保期未明确","fix_hint":"补充质保期"}]',
        findings: [
          {
            evidence: '质保期未明确',
            fix_hint: '补充质保期',
          },
        ],
      });
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    const agentMessages = conversation?.messages.filter(
      (message) => message.metadata?.messageKind === 'agent-step'
    );
    const draftMessage = agentMessages?.find(
      (message) => message.metadata?.agentStepNode === 'content_generate_agent'
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

    expect(agentMessages).toHaveLength(4);
    expect(agentMessages?.map((message) => message.metadata?.agentStepNode)).toEqual([
      'content_generate_agent',
      'content_verify_agent',
      'content_revise_agent',
      'content_verify_agent',
    ]);
    expect(agentMessages?.[0].content).toBe('智能体初稿');
    expect(draftMessage?.content).toBe('智能体初稿');
    expect(draftMessage?.metadata?.agentStepNode).toBe('content_generate_agent');
    expect(firstAuditMessage?.content).toBe('[{"evidence":"缺少供货范围","fix_hint":"补充供货范围说明"}]');
    expect(firstAuditMessage?.metadata?.agentStepNode).toBe('content_verify_agent');
    expect(firstAuditMessage?.metadata?.agentStepRound).toBe(1);
    expect(firstAuditMessage?.metadata?.agentStepAuditRounds).toHaveLength(1);
    expect(revisionMessage?.content).toBe('第一轮 AI 修改内容');
    expect(revisionMessage?.metadata?.agentStepNode).toBe('content_revise_agent');
    expect(revisionMessage?.metadata?.agentStepRound).toBe(1);
    expect(secondAuditMessage?.content).toBe('[{"evidence":"质保期未明确","fix_hint":"补充质保期"}]');
    expect(secondAuditMessage?.metadata?.agentStepNode).toBe('content_verify_agent');
    expect(secondAuditMessage?.metadata?.agentStepRound).toBe(2);
    expect(secondAuditMessage?.metadata?.agentStepAuditRounds).toHaveLength(1);
  });

  it('appends comment_agent AIMessage contents to one process card and preserves them on final', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-1', {
        task_kind: 'comment_supplement',
        status: 'running',
        current_node: 'comment_agent',
      });
      useChatStore.getState().upsertAgentStepMessage('task-1', {
        timestamp: new Date().toISOString(),
        task_id: 'task-1',
        task_kind: 'comment_supplement',
        step_type: 'stream',
        round: 1,
        node: 'comment_agent',
        is_complete: false,
        content: '开始校验批注锚点',
        findings: [],
      });
      useChatStore.getState().upsertAgentStepMessage('task-1', {
        timestamp: new Date().toISOString(),
        task_id: 'task-1',
        task_kind: 'comment_supplement',
        step_type: 'stream',
        round: 1,
        node: 'comment_agent',
        is_complete: false,
        content: '批注锚点校验完成',
        findings: [],
      });
      useChatStore.getState().upsertAgentStepMessage('task-1', {
        timestamp: new Date().toISOString(),
        task_id: 'task-1',
        task_kind: 'comment_supplement',
        step_type: 'stream',
        round: 1,
        node: 'comment_agent',
        is_complete: true,
        content: undefined,
        findings: [],
      });
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    const agentMessages = conversation?.messages.filter(
      (message) => message.metadata?.messageKind === 'agent-step'
    );

    expect(agentMessages).toHaveLength(1);
    expect(agentMessages?.[0].metadata?.agentStepNode).toBe('comment_agent');
    expect(agentMessages?.[0].metadata?.taskKind).toBe('comment_supplement');
    expect(agentMessages?.[0].content).toBe('开始校验批注锚点\n\n批注锚点校验完成');
    expect(agentMessages?.[0].status).toBe('completed');
  });

  it('does not render empty verify findings as JSON until content or completion findings exist', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-1', {
        task_kind: 'generate',
        status: 'running',
      });
      useChatStore.getState().upsertAgentStepMessage('task-1', {
        timestamp: new Date().toISOString(),
        task_id: 'task-1',
        task_kind: 'generate',
        step_type: 'stream',
        round: 1,
        node: 'content_verify_agent',
        is_complete: false,
        content: '',
        findings: [],
      });
    });

    let conversation = useChatStore.getState().getCurrentConversation();
    let verifyMessage = conversation?.messages.find(
      (message) => message.metadata?.agentStepNode === 'content_verify_agent'
    );

    expect(verifyMessage?.content).toBe('');
    expect(verifyMessage?.status).toBe('generating');

    act(() => {
      useChatStore.getState().upsertAgentStepMessage('task-1', {
        timestamp: new Date().toISOString(),
        task_id: 'task-1',
        task_kind: 'generate',
        step_type: 'stream',
        round: 1,
        node: 'content_verify_agent',
        is_complete: true,
        content: '[]',
        findings: [],
      });
    });

    conversation = useChatStore.getState().getCurrentConversation();
    verifyMessage = conversation?.messages.find(
      (message) => message.metadata?.agentStepNode === 'content_verify_agent'
    );

    expect(verifyMessage?.content).toBe('[]');
    expect(verifyMessage?.status).toBe('completed');
  });

  it('keeps completed agent-step cards completed when a late stream snapshot arrives', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-1', {
        task_kind: 'generate',
        status: 'running',
      });
      useChatStore.getState().upsertAgentStepMessage('task-1', {
        timestamp: new Date().toISOString(),
        task_id: 'task-1',
        task_kind: 'generate',
        step_type: 'stream',
        round: 1,
        node: 'content_verify_agent',
        is_complete: true,
        content: '[{"evidence":"缺少供货范围","fix_hint":"补充供货范围说明"}]',
        findings: [
          {
            evidence: '缺少供货范围',
            fix_hint: '补充供货范围说明',
          },
        ],
      });
      useChatStore.getState().upsertAgentStepMessage('task-1', {
        timestamp: new Date().toISOString(),
        task_id: 'task-1',
        task_kind: 'generate',
        step_type: 'stream',
        round: 1,
        node: 'content_verify_agent',
        is_complete: false,
        content: '[{"evidence":"迟到的旧快照","fix_hint":"不应覆盖完成卡片"}]',
        findings: [
          {
            evidence: '迟到的旧快照',
            fix_hint: '不应覆盖完成卡片',
          },
        ],
      });
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    const verifyMessage = conversation?.messages.find(
      (message) => message.metadata?.agentStepNode === 'content_verify_agent'
    );

    expect(verifyMessage?.status).toBe('completed');
    expect(verifyMessage?.content).toBe(
      '[{"evidence":"缺少供货范围","fix_hint":"补充供货范围说明"}]'
    );
    expect(verifyMessage?.metadata?.agentStepFindings).toEqual([
      {
        evidence: '缺少供货范围',
        fix_hint: '补充供货范围说明',
      },
    ]);
  });

  it('keeps incomplete agent-step card lightweight when the next agent step starts', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-1', {
        task_kind: 'generate',
        status: 'running',
      });
      useChatStore.getState().upsertAgentStepMessage('task-1', {
        timestamp: new Date().toISOString(),
        task_id: 'task-1',
        task_kind: 'generate',
        step_type: 'stream',
        round: 1,
        node: 'content_verify_agent',
        is_complete: false,
        content: '[{"evidence":"缺少供货范围","fix_hint":"补充供货范围说明"}]',
        findings: [
          {
            evidence: '缺少供货范围',
            fix_hint: '补充供货范围说明',
          },
        ],
      });
      useChatStore.getState().upsertAgentStepMessage('task-1', {
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
            evidence: '缺少供货范围',
            fix_hint: '补充供货范围说明',
          },
        ],
      });
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    const verifyMessage = conversation?.messages.find(
      (message) => message.metadata?.agentStepNode === 'content_verify_agent'
    );
    const revisionMessage = conversation?.messages.find(
      (message) => message.metadata?.agentStepNode === 'content_revise_agent'
    );

    expect(verifyMessage?.status).toBe('completed');
    expect(verifyMessage?.content).toBe('');
    expect(revisionMessage?.status).toBe('completed');
  });

  it('removes duplicated task-content card when agent-step cards start streaming', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-1', {
        task_kind: 'generate',
        status: 'running',
      });
      useChatStore.getState().ensureTaskLogMessage('task-1');
      useChatStore.getState().ensureTaskContentMessage('task-1', {
        content: '普通 LLM 快照',
        status: 'generating',
      });
      useChatStore.getState().upsertAgentStepMessage('task-1', {
        timestamp: new Date().toISOString(),
        task_id: 'task-1',
        task_kind: 'generate',
        step_type: 'stream',
        round: 1,
        node: 'content_generate_agent',
        is_complete: true,
        content: '智能体初稿',
        findings: [],
      });
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    const group = useChatStore.getState().findTaskMessageGroup('task-1');
    const agentMessages = conversation?.messages.filter(
      (message) => message.metadata?.messageKind === 'agent-step'
    );

    expect(group?.contentMessage).toBeUndefined();
    expect(agentMessages).toHaveLength(1);
    expect(agentMessages?.[0].content).toBe('智能体初稿');
    expect(conversation?.messages.some((message) => message.content === '普通 LLM 快照')).toBe(
      false
    );
  });

  it('completeTask persists two cards and appends one download card', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-1');
      useChatStore.getState().ensureTaskLogMessage('task-1');
      useChatStore.getState().completeTask(
        'task-1',
        'D:/UploadFiles/output.docx',
        'output.docx',
        {
          logs: [
            {
              id: 'log-1',
              timestamp: Date.now(),
              level: 'info',
              message: '处理完成',
            },
          ],
          aiText: '最终内容',
          aiComplete: true,
        },
        {
          summary: '样式回填: 抽取=2, 尝试=2, 成功=1, 跳过=1, 失败=0',
          extracted: 2,
          attempted: 2,
          applied: 1,
          skipped: 1,
          failed: 0,
          applied_by_style: { bold: 1 },
          skipped_by_reason: { low_confidence: 1 },
        },
        {
          summary: 'AI 批注写入: 生成=3, 成功=1, 跳过=0, 失败=2',
          generated: 3,
          added: 1,
          failed: 2,
          skipped: 0,
          warning: true,
        }
      );
    });

    const group = useChatStore.getState().findTaskMessageGroup('task-1');
    expect(group?.logMessage?.status).toBe('completed');
    expect(group?.contentMessage?.status).toBe('completed');
    expect(group?.contentMessage?.content).toBe('最终内容');
    expect(group?.downloadMessage?.metadata?.messageKind).toBe('task-download');
    expect(group?.downloadMessage?.metadata?.outputFile).toBe('D:/UploadFiles/output.docx');
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
      summary: 'AI 批注写入: 生成=3, 成功=1, 跳过=0, 失败=2',
      generated: 3,
      added: 1,
      failed: 2,
      skipped: 0,
      warning: true,
    });
  });

  it('completeTask keeps agent-step process cards and appends the download card', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-1', {
        task_kind: 'generate',
        status: 'running',
      });
      useChatStore.getState().ensureTaskLogMessage('task-1');
      useChatStore.getState().ensureTaskContentMessage('task-1', {
        content: '重复的普通内容',
        status: 'generating',
      });
      useChatStore.getState().upsertAgentStepMessage('task-1', {
        timestamp: new Date().toISOString(),
        task_id: 'task-1',
        task_kind: 'generate',
        step_type: 'stream',
        round: 1,
        node: 'content_generate_agent',
        is_complete: true,
        content: '智能体初稿',
        findings: [],
      });
      useChatStore.getState().upsertAgentStepMessage('task-1', {
        timestamp: new Date().toISOString(),
        task_id: 'task-1',
        task_kind: 'generate',
        step_type: 'stream',
        round: 1,
        node: 'content_revise_agent',
        is_complete: true,
        content: '修复后的正文',
        findings: [],
      });
      useChatStore.getState().completeTask('task-1', 'D:/UploadFiles/output.docx', 'output.docx', {
        logs: [],
        aiText: '',
        aiComplete: true,
      });
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    const agentMessages = conversation?.messages.filter(
      (message) => message.metadata?.messageKind === 'agent-step'
    );
    const group = useChatStore.getState().findTaskMessageGroup('task-1');

    expect(agentMessages).toHaveLength(2);
    expect(agentMessages?.map((message) => message.content)).toEqual([
      '智能体初稿',
      '修复后的正文',
    ]);
    expect(group?.contentMessage).toBeUndefined();
    expect(group?.downloadMessage?.metadata?.messageKind).toBe('task-download');
    expect(group?.downloadMessage?.metadata?.outputFile).toBe('D:/UploadFiles/output.docx');
    expect(conversation?.messages.some((message) => message.content === '重复的普通内容')).toBe(
      false
    );
  });

  it('failTask keeps agent-step process cards and does not append task-content', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-1', {
        task_kind: 'generate',
        status: 'running',
        current_node: 'content_agent',
      });
      useChatStore.getState().ensureTaskLogMessage('task-1');
      useChatStore.getState().upsertAgentStepMessage('task-1', {
        timestamp: new Date().toISOString(),
        task_id: 'task-1',
        task_kind: 'generate',
        step_type: 'stream',
        round: 1,
        node: 'content_generate_agent',
        is_complete: true,
        content: '智能体初稿',
        findings: [],
      });
      useChatStore.getState().failTask('task-1', 'Request timed out.', {
        logs: [
          {
            id: 'log-error',
            timestamp: Date.now(),
            level: 'error',
            message: 'Request timed out.',
          },
        ],
        aiText: '不应生成普通 AI 内容卡',
        aiComplete: false,
      });
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    const agentMessages = conversation?.messages.filter(
      (message) => message.metadata?.messageKind === 'agent-step'
    );
    const group = useChatStore.getState().findTaskMessageGroup('task-1');

    expect(agentMessages).toHaveLength(1);
    expect(agentMessages?.[0].content).toBe('智能体初稿');
    expect(group?.logMessage?.status).toBe('error');
    expect(group?.logMessage?.metadata?.logs).toEqual(
      expect.arrayContaining([expect.objectContaining({ message: 'Request timed out.' })])
    );
    expect(group?.contentMessage).toBeUndefined();
    expect(
      conversation?.messages.some((message) => message.content === '不应生成普通 AI 内容卡')
    ).toBe(false);
  });

  it('cancelTask keeps agent-step process cards and does not append task-content', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-1', {
        task_kind: 'generate',
        status: 'running',
        current_node: 'content_agent',
      });
      useChatStore.getState().ensureTaskLogMessage('task-1');
      useChatStore.getState().upsertAgentStepMessage('task-1', {
        timestamp: new Date().toISOString(),
        task_id: 'task-1',
        task_kind: 'generate',
        step_type: 'stream',
        round: 1,
        node: 'content_generate_agent',
        is_complete: true,
        content: '智能体初稿',
        findings: [],
      });
      useChatStore.getState().cancelTask('task-1', {
        logs: [],
        aiText: '不应生成普通 AI 内容卡',
        aiComplete: false,
      });
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    const group = useChatStore.getState().findTaskMessageGroup('task-1');

    expect(group?.logMessage?.status).toBe('cancelled');
    expect(group?.contentMessage).toBeUndefined();
    expect(
      conversation?.messages.some((message) => message.content === '不应生成普通 AI 内容卡')
    ).toBe(false);
  });

  it('queued terminal task does not create any chat cards', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-fail');
      useChatStore.getState().failTask('task-fail', '生成失败');
      useChatStore.getState().startTask('conv-1', 'task-cancel');
      useChatStore.getState().cancelTask('task-cancel');
    });

    const failGroup = useChatStore.getState().findTaskMessageGroup('task-fail');
    const cancelGroup = useChatStore.getState().findTaskMessageGroup('task-cancel');
    const conversation = useChatStore.getState().getCurrentConversation();

    expect(failGroup).toBeNull();
    expect(cancelGroup).toBeNull();
    expect(conversation?.messages).toHaveLength(0);
    expect(conversation?.currentTaskId).toBeUndefined();
    expect(useChatStore.getState().activeTaskIds).toHaveLength(0);
  });

  it('does not downgrade a cancelled task-log message back to generating', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-1', {
        task_kind: 'rewrite',
        status: 'running',
      });
      useChatStore.getState().ensureTaskLogMessage('task-1');
      useChatStore.getState().cancelTask('task-1', {
        logs: [
          {
            id: 'log-1',
            timestamp: Date.now(),
            level: 'info',
            message: '任务已取消',
          },
        ],
      });
      useChatStore.getState().ensureTaskLogMessage('task-1', { status: 'generating' });
    });

    const group = useChatStore.getState().findTaskMessageGroup('task-1');
    expect(group?.logMessage?.status).toBe('cancelled');
    expect(group?.logMessage?.metadata?.messageKind).toBe('task-log');
    expect(group?.logMessage?.metadata?.taskKind).toBe('rewrite');
  });

  it('interrupts active tasks on backend restart while preserving streamed logs and ai text', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-1', {
        task_kind: 'rewrite',
        status: 'running',
      });
      useChatStore.getState().ensureTaskLogMessage('task-1');
      useChatStore.getState().updateConversationDraft('conv-1', {
        chat_input: '',
        pending_rewrite_prompt: '请补充质保条款',
        pending_rewrite_task_id: 'task-1',
      });
      useChatStreamStore.getState().replaceStream('task-1', {
        logs: [
          {
            id: 'log-running',
            timestamp: Date.now(),
            level: 'info',
            message: '正在修改',
          },
        ],
        aiText: '已生成的修改内容',
        aiComplete: false,
      });
      useChatTaskSessionStore.getState().upsertSession('task-1', { lastEventId: '42' });
      useChatStore.getState().handleBackendRestart();
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    const group = useChatStore.getState().findTaskMessageGroup('task-1');
    const draft = useChatStore.getState().getConversationDraft('conv-1');

    expect(conversation?.currentTaskId).toBeUndefined();
    expect(useChatStore.getState().activeTaskIds).toHaveLength(0);
    expect(group?.logMessage?.status).toBe('error');
    expect(group?.contentMessage?.status).toBe('error');
    expect(group?.contentMessage?.content).toBe('已生成的修改内容');
    expect(group?.contentMessage?.error).toBe('服务已重启，任务已中断，可重试');
    expect(group?.contentMessage?.metadata?.localTaskReason).toBe('backend_restart');
    expect(group?.logMessage?.metadata?.logs).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ message: '正在修改' }),
        expect.objectContaining({ message: '服务已重启，任务已中断，可重试' }),
      ])
    );
    expect(draft?.pending_rewrite_task_id).toBeUndefined();
    expect(draft?.pending_rewrite_prompt).toBeUndefined();
    expect(draft?.chat_input).toBe('请补充质保条款');
    expect(useChatStreamStore.getState().streams['task-1']).toBeUndefined();
    expect(useChatTaskSessionStore.getState().sessions['task-1']).toBeUndefined();
  });

  it('marks legacy generating task messages as interrupted when discarding stale tasks', () => {
    act(() => {
      useChatStore.setState((state) => ({
        conversations: state.conversations.map((conversation) => ({
          ...conversation,
          currentTaskId: 'task-1',
          messages: [
            {
              id: 'msg-legacy',
              conversationId: conversation.id,
              type: 'ai',
              content: {
                logs: [],
                aiContent: {
                  text: '',
                  timestamp: 1,
                  isComplete: false,
                },
              },
              timestamp: 1,
              status: 'generating',
              taskId: 'task-1',
            },
          ],
        })),
        activeTaskIds: ['task-1'],
        taskSummaries: {
          'task-1': {
            task_id: 'task-1',
            status: 'running',
            updated_at: 1,
          },
        },
      }));

      useChatStore.getState().discardStaleTask('task-1');
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    const messages = conversation?.messages ?? [];
    const legacyMessage = messages.find((message) => message.id === 'msg-legacy');

    expect(conversation?.currentTaskId).toBeUndefined();
    expect(useChatStore.getState().activeTaskIds).toHaveLength(0);
    expect(messages.filter((message) => message.status === 'generating')).toHaveLength(0);
    expect(legacyMessage?.status).toBe('error');
    expect(legacyMessage?.error).toBe('服务已重启，任务已中断，可重试');
    expect(legacyMessage?.metadata?.localTaskReason).toBe('backend_restart');
  });
});
