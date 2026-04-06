import { act, waitFor } from '@testing-library/react';
import { useChatStore } from '@/stores/chatStore';
import { useHistoryStore } from '@/stores/historyStore';
import { useChatTaskSessionStore } from '@/stores/chatTaskSessionStore';

function resetStores() {
  window.localStorage.clear();
  window.sessionStorage.clear();

  useChatStore.setState({
    conversations: [],
    currentConversationId: null,
    activeTaskIds: [],
    taskMessageMap: {},
    conversationDrafts: {},
    taskSummaries: {},
    isLoading: false,
    error: null,
    selectedTenderType: null,
  });
  useHistoryStore.setState({ history: [] });
  useChatTaskSessionStore.setState({ sessions: {} });
}

describe('current-page session persistence', () => {
  beforeEach(() => {
    resetStores();
  });

  it('persists current-page chat conversations in sessionStorage only', async () => {
    act(() => {
      useChatStore.getState().createConversation('SESSION-CHAT-001', 'xjcg');
    });

    await waitFor(() => {
      expect(window.sessionStorage.getItem('chat-storage')).toContain('SESSION-CHAT-001');
    });
    expect(window.localStorage.getItem('chat-storage')).toBeNull();
  });

  it('persists current-page generation history in sessionStorage only', async () => {
    act(() => {
      useHistoryStore.getState().addToHistory({
        taskId: 'task-history-1',
        tenderNo: 'SESSION-HISTORY-001',
        tenderType: 'xjcg',
        tenderTypeName: '询价采购',
        status: 'running',
        model: 'deepseek',
        progressPercent: 10,
      });
    });

    await waitFor(() => {
      expect(window.sessionStorage.getItem('tender-history-storage')).toContain(
        'SESSION-HISTORY-001'
      );
    });
    expect(window.localStorage.getItem('tender-history-storage')).toBeNull();
  });

  it('persists current-page task sessions in sessionStorage only', async () => {
    act(() => {
      useChatTaskSessionStore.getState().upsertSession('task-session-1', { lastEventId: '7' });
    });

    await waitFor(() => {
      expect(window.sessionStorage.getItem('chat-task-session-storage')).toContain(
        'task-session-1'
      );
    });
    expect(window.localStorage.getItem('chat-task-session-storage')).toBeNull();
  });
});
