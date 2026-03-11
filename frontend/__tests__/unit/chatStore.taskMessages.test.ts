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

  it('completeTask persists two cards and appends one download card', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-1');
      useChatStore.getState().ensureTaskLogMessage('task-1');
      useChatStore.getState().completeTask('task-1', 'D:/UploadFiles/output.docx', 'output.docx', {
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
      });
    });

    const group = useChatStore.getState().findTaskMessageGroup('task-1');
    expect(group?.logMessage?.status).toBe('completed');
    expect(group?.contentMessage?.status).toBe('completed');
    expect(group?.contentMessage?.content).toBe('最终内容');
    expect(group?.downloadMessage?.metadata?.messageKind).toBe('task-download');
    expect(group?.downloadMessage?.metadata?.outputFile).toBe('D:/UploadFiles/output.docx');
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
});
