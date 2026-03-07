import { act } from '@testing-library/react';
import { useChatStore } from '@/stores/chatStore';

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
});
