import { act } from '@testing-library/react';
import { useChatStore } from '@/stores/chatStore';

function resetStore() {
  window.localStorage.clear();
  window.sessionStorage.clear();

  useChatStore.setState((state) => ({
    ...state,
    conversations: [],
    currentConversationId: null,
    activeTaskIds: [],
    taskMessageMap: {},
    conversationDrafts: {},
    taskSummaries: {},
    selectedTenderType: null,
    error: null,
    isLoading: false,
  }));
}

describe('chatStore conversation scoped selectors', () => {
  beforeEach(() => {
    resetStore();
  });

  it('does not lock current conversation when only other conversations have active tasks', () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          id: 'conv-current',
          title: 'CURRENT',
          tenderType: 'xjcg',
          createdAt: 1,
          updatedAt: 1,
          messages: [],
        },
        {
          id: 'conv-other',
          title: 'OTHER',
          tenderType: 'xjcg',
          createdAt: 2,
          updatedAt: 2,
          messages: [],
          currentTaskId: 'task-2',
        },
      ],
      currentConversationId: 'conv-current',
      activeTaskIds: ['task-2'],
    }));

    const store = useChatStore.getState();
    expect(store.currentConversationActiveTask()).toBeNull();
    expect(store.currentConversationIsBusy()).toBe(false);
    expect(store.latestActiveTaskId()).toBe('task-2');
    expect(store.otherActiveTaskCount()).toBe(0);
  });

  it('reports current conversation busy only for its own bound task', () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          id: 'conv-current',
          title: 'CURRENT',
          tenderType: 'xjcg',
          createdAt: 1,
          updatedAt: 1,
          messages: [],
          currentTaskId: 'task-1',
        },
        {
          id: 'conv-other',
          title: 'OTHER',
          tenderType: 'xjcg',
          createdAt: 2,
          updatedAt: 2,
          messages: [],
          currentTaskId: 'task-2',
        },
      ],
      currentConversationId: 'conv-current',
      activeTaskIds: ['task-1', 'task-2'],
    }));

    const store = useChatStore.getState();
    expect(store.currentConversationActiveTask()).toBe('task-1');
    expect(store.currentConversationIsBusy()).toBe(true);
    expect(store.latestActiveTaskId()).toBe('task-2');
    expect(store.otherActiveTaskCount()).toBe(1);
  });

  it('keeps drafts isolated per conversation when switching', () => {
    let convA = '';
    let convB = '';

    act(() => {
      convA = useChatStore.getState().createConversation('TN-001', 'xjcg');
      convB = useChatStore.getState().createConversation('TN-002', 'xjcg');
    });

    act(() => {
      useChatStore.getState().updateConversationDraft(convA, {
        tender_no: 'TN-001',
        model: 'deepseek',
      });
      useChatStore.getState().updateConversationDraft(convB, {
        tender_no: 'TN-002',
        model: 'qwen',
      });
    });

    expect(useChatStore.getState().getConversationDraft(convA)?.tender_no).toBe('TN-001');
    expect(useChatStore.getState().getConversationDraft(convA)?.model).toBe('deepseek');
    expect(useChatStore.getState().getConversationDraft(convB)?.tender_no).toBe('TN-002');
    expect(useChatStore.getState().getConversationDraft(convB)?.model).toBe('qwen');
  });

  it('allows multiple independent conversations with same type and tender number', () => {
    let convA = '';
    let convB = '';

    act(() => {
      convA = useChatStore.getState().createConversation('TN-SAME', 'xjcg');
      convB = useChatStore.getState().createConversation('TN-SAME', 'xjcg');
    });

    const conversations = useChatStore.getState().conversations;
    expect(convA).not.toBe(convB);
    expect(conversations.filter((conversation) => conversation.title === 'TN-SAME')).toHaveLength(2);
  });

  it('initializes new conversations with deepseek as the draft model', () => {
    let conversationId = '';

    act(() => {
      conversationId = useChatStore.getState().createConversation('TN-DEFAULT', 'xjcg');
    });

    expect(useChatStore.getState().getConversationDraft(conversationId)?.model).toBe('deepseek');
  });

  it('finds the most recent matching conversation by normalized tender number and type', () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          id: 'conv-xjcg-old',
          title: '0811-DSITC253505',
          tenderType: 'xjcg',
          createdAt: 1,
          updatedAt: 1,
          messages: [],
        },
        {
          id: 'conv-xjcg-new',
          title: '自定义标题',
          tenderType: 'xjcg',
          createdAt: 2,
          updatedAt: 20,
          messages: [],
        },
        {
          id: 'conv-gngk',
          title: '0811-DSITC253505',
          tenderType: 'gngk',
          createdAt: 3,
          updatedAt: 30,
          messages: [],
        },
      ],
      conversationDrafts: {
        'conv-xjcg-new': {
          tender_no: ' 0811-dsitc253505 ',
          model: 'deepseek',
        },
      },
    }));

    const store = useChatStore.getState();
    expect(store.findConversationByTenderNo('0811-DSITC253505', 'xjcg')?.id).toBe(
      'conv-xjcg-new'
    );
    expect(store.findConversationByTenderNo('0811-dsitc253505', 'gngk')?.id).toBe('conv-gngk');
  });

  it('returns the most recent conversation for a type by updatedAt', () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          id: 'conv-updated-late',
          title: 'UPDATED-LATE',
          tenderType: 'xjcg',
          createdAt: 1,
          updatedAt: 50,
          messages: [],
        },
        {
          id: 'conv-created-late',
          title: 'CREATED-LATE',
          tenderType: 'xjcg',
          createdAt: 99,
          updatedAt: 20,
          messages: [],
        },
      ],
    }));

    expect(useChatStore.getState().getMostRecentConversationByType('xjcg')?.id).toBe(
      'conv-updated-late'
    );
  });

  it('falls back to the same tender type conversation with the latest updatedAt after deletion', () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          id: 'conv-current',
          title: 'CURRENT',
          tenderType: 'xjcg',
          createdAt: 1,
          updatedAt: 10,
          messages: [],
        },
        {
          id: 'conv-fallback-new',
          title: 'FALLBACK-NEW',
          tenderType: 'xjcg',
          createdAt: 2,
          updatedAt: 40,
          messages: [],
        },
        {
          id: 'conv-fallback-old',
          title: 'FALLBACK-OLD',
          tenderType: 'xjcg',
          createdAt: 3,
          updatedAt: 15,
          messages: [],
        },
        {
          id: 'conv-other-type',
          title: 'OTHER-TYPE',
          tenderType: 'gngk',
          createdAt: 4,
          updatedAt: 100,
          messages: [],
        },
      ],
      currentConversationId: 'conv-current',
      selectedTenderType: 'xjcg',
    }));

    useChatStore.getState().deleteConversation('conv-current');

    const state = useChatStore.getState();
    expect(state.currentConversationId).toBe('conv-fallback-new');
    expect(state.selectedTenderType).toBe('xjcg');
  });
});
