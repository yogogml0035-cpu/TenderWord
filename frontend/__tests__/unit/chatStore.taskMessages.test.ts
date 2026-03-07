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
    isLoading: false,
    error: null,
    concurrentTaskWarning: false,
    selectedTenderType: 'xjcg',
  });
}

describe('chatStore task message grouping', () => {
  beforeEach(() => {
    resetStore();
  });

  it('startTask only creates task-log generating message', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-1');
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    expect(conversation?.messages).toHaveLength(1);
    expect(conversation?.messages[0].metadata?.messageKind).toBe('task-log');
    expect(conversation?.messages[0].status).toBe('generating');
  });

  it('ensureTaskContentMessage lazily creates task-content message', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-1');
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

  it('failTask and cancelTask do not create download card', () => {
    act(() => {
      useChatStore.getState().startTask('conv-1', 'task-fail');
      useChatStore.getState().failTask('task-fail', '生成失败', {
        logs: [],
        aiText: '失败内容',
      });
      useChatStore.getState().startTask('conv-1', 'task-cancel');
      useChatStore.getState().cancelTask('task-cancel', {
        logs: [],
        aiText: '取消前内容',
      });
    });

    const failGroup = useChatStore.getState().findTaskMessageGroup('task-fail');
    const cancelGroup = useChatStore.getState().findTaskMessageGroup('task-cancel');

    expect(failGroup?.logMessage?.status).toBe('error');
    expect(failGroup?.contentMessage?.status).toBe('error');
    expect(failGroup?.contentMessage?.error).toBe('生成失败');
    expect(failGroup?.downloadMessage).toBeUndefined();

    expect(cancelGroup?.logMessage?.status).toBe('cancelled');
    expect(cancelGroup?.contentMessage?.status).toBe('cancelled');
    expect(cancelGroup?.downloadMessage).toBeUndefined();
  });
});
