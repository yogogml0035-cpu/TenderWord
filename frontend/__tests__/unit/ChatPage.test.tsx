import { act, render, screen, waitFor } from '@testing-library/react';
import ChatPage from '@/app/tender/page';
import { generateConversationTitle } from '@/lib/chat-utils';
import { useChatStore } from '@/stores/chatStore';
import { useChatStreamStore } from '@/stores/chatStreamStore';
import { useChatTaskSessionStore } from '@/stores/chatTaskSessionStore';
import type { TenderType } from '@/types';
import type { ConversationHeartbeatData, TenderData, TenderLookupResponse } from '@/types/api';

const mockFetchTenderDataWithType = jest.fn();
const mockSendConversationHeartbeat = jest.fn();
const mockUseUrlParams = jest.fn();

const buildTenderData = (overrides?: Partial<TenderData>): TenderData => ({
  project_name: '测试项目',
  project_number: 'TEST-001',
  project_content: '测试内容',
  bzj_rule: '保证金规则',
  buyer_name: '测试采购人',
  project_zbr_xbr: '张三',
  zbr_xbr_tel: '13800138000',
  zbr_pinyin: 'zhangsan',
  shell_start_date: '2024-01-01',
  shell_end_date: '2024-12-31',
  submit_date: '2024-12-31',
  platform: '测试平台',
  service_fee: '1000',
  ...overrides,
});

jest.mock('@/hooks/useHydrated', () => ({
  useHydrated: () => true,
}));

jest.mock('@/hooks/useUrlParams', () => ({
  useUrlParams: () => mockUseUrlParams(),
}));

jest.mock('@/components/chat/TenderTypeSidebar', () => ({
  TenderTypeSidebar: () => <div data-testid="tender-type-sidebar">sidebar</div>,
}));

jest.mock('@/components/chat/FormPanel', () => ({
  FormPanel: () => <div data-testid="form-panel">form-panel</div>,
}));

jest.mock('@/components/chat/ChatPanel', () => ({
  ChatPanel: () => <div data-testid="chat-panel">chat-panel</div>,
}));

jest.mock('@/lib/api', () => ({
  fetchTenderDataWithType: (...args: unknown[]) => mockFetchTenderDataWithType(...args),
  sendConversationHeartbeat: (...args: unknown[]) => mockSendConversationHeartbeat(...args),
}));

const buildTenderLookupResponse = (
  overrides?: Partial<TenderLookupResponse>
): TenderLookupResponse => ({
  data: buildTenderData(),
  type: {
    tender_lx: 0,
    purchase_method: 0,
    fund_lx: 1,
  },
  ...overrides,
});

function createHeartbeat(instanceId: string, rewriteAvailable: boolean): ConversationHeartbeatData {
  return {
    conversation_id: 'conv-1',
    alive: true,
    instance_id: instanceId,
    server_time: new Date().toISOString(),
    rewrite_available: rewriteAvailable,
  };
}

describe('ChatPage', () => {
  beforeEach(() => {
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
      conversationDrafts: {
        'conv-1': {
          pending_rewrite_prompt: '请补充售后条款',
          pending_rewrite_task_id: 'task-1',
        },
      },
      taskSummaries: {
        'task-1': {
          task_id: 'task-1',
          task_kind: 'rewrite',
          status: 'running',
          updated_at: Date.now(),
        },
      },
      unreadConversationResults: {},
      isLoading: false,
      error: null,
      selectedTenderType: 'xjcg',
    }));

    useChatStreamStore.setState({
      streams: {
        'task-1': {
          logs: [
            {
              id: 'log-stream-1',
              timestamp: Date.now(),
              level: 'info',
              message: '正在修改',
            },
          ],
          aiText: '保留中的修改内容',
          aiComplete: false,
          lastEventId: '42',
        },
      },
    });
    useChatTaskSessionStore.setState({
      sessions: {
        'task-1': {
          taskId: 'task-1',
          lastEventId: '42',
        },
      },
    });

    mockFetchTenderDataWithType.mockReset();
    mockSendConversationHeartbeat.mockReset();
    mockUseUrlParams.mockReset();
    mockUseUrlParams.mockReturnValue({
      tenderno: undefined,
      tenderType: undefined,
      isValid: false,
      hasParams: false,
    });
    mockSendConversationHeartbeat.mockResolvedValue(createHeartbeat('instance-a', true));
  });

  it('keeps the current conversation and silently degrades active tasks when backend instance changes', async () => {
    mockSendConversationHeartbeat
      .mockResolvedValueOnce(createHeartbeat('instance-a', true))
      .mockResolvedValueOnce(createHeartbeat('instance-b', false));

    render(<ChatPage />);

    await waitFor(() => {
      expect(mockSendConversationHeartbeat).toHaveBeenCalledTimes(1);
    });

    await act(async () => {
      window.dispatchEvent(new Event('focus'));
      await Promise.resolve();
    });

    await waitFor(() => {
      const conversation = useChatStore.getState().getCurrentConversation();
      const group = useChatStore.getState().findTaskMessageGroup('task-1');
      const draft = useChatStore.getState().getConversationDraft('conv-1');

      expect(mockSendConversationHeartbeat).toHaveBeenCalledTimes(2);
      expect(conversation?.id).toBe('conv-1');
      expect(conversation?.currentTaskId).toBeUndefined();
      expect(group?.logMessage?.status).toBe('error');
      expect(group?.contentMessage?.status).toBe('error');
      expect(group?.contentMessage?.content).toBe('保留中的修改内容');
      expect(draft?.chat_input).toBe('请补充售后条款');
      expect(useChatStore.getState().activeTaskIds).toHaveLength(0);
      expect(useChatTaskSessionStore.getState().sessions['task-1']).toBeUndefined();
      expect(useChatStreamStore.getState().streams['task-1']).toBeUndefined();
    });

    expect(screen.getByTestId('chat-panel')).toBeInTheDocument();
    expect(screen.queryByText('检测到服务已重启')).not.toBeInTheDocument();
    expect(screen.queryByText('确认并重置会话')).not.toBeInTheDocument();
  });

  it('reuses an existing matching conversation without refetching when draft data already exists', async () => {
    const cachedTenderData = buildTenderData();
    mockUseUrlParams.mockReturnValue({
      tenderno: '0811-DSITC253505',
      tenderType: 'xjcg' as TenderType,
      isValid: true,
      hasParams: true,
    });

    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          id: 'conv-existing',
          title: '自定义标题',
          tenderType: 'xjcg',
          createdAt: 1,
          updatedAt: 2,
          messages: [],
        },
      ],
      currentConversationId: null,
      activeTaskIds: [],
      taskMessageMap: {},
      conversationDrafts: {
        'conv-existing': {
          tender_no: '0811-dsitc253505',
          tender_data: cachedTenderData,
          model: 'deepseek',
        },
      },
      taskSummaries: {},
      unreadConversationResults: {},
      isLoading: false,
      error: null,
      selectedTenderType: null,
    }));

    render(<ChatPage />);

    await waitFor(() => {
      expect(useChatStore.getState().currentConversationId).toBe('conv-existing');
    });

    expect(useChatStore.getState().conversations).toHaveLength(1);
    expect(useChatStore.getState().selectedTenderType).toBe('xjcg');
    expect(useChatStore.getState().getConversationDraft('conv-existing')?.tender_fetch).toEqual({
      status: 'success',
    });
    expect(mockFetchTenderDataWithType).not.toHaveBeenCalled();
  });

  it('reuses an existing matching conversation, fetches missing tender data, and preserves a custom title', async () => {
    const fetchedTenderData = buildTenderData();
    mockUseUrlParams.mockReturnValue({
      tenderno: '0811-DSITC253505',
      tenderType: 'xjcg' as TenderType,
      isValid: true,
      hasParams: true,
    });
    mockFetchTenderDataWithType.mockResolvedValue(
      buildTenderLookupResponse({
        data: fetchedTenderData,
      })
    );

    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          id: 'conv-existing',
          title: '自定义标题',
          tenderType: 'xjcg',
          createdAt: 1,
          updatedAt: 2,
          messages: [],
        },
      ],
      currentConversationId: null,
      activeTaskIds: [],
      taskMessageMap: {},
      conversationDrafts: {
        'conv-existing': {
          tender_no: '0811-dsitc253505',
          model: 'deepseek',
        },
      },
      taskSummaries: {},
      unreadConversationResults: {},
      isLoading: false,
      error: null,
      selectedTenderType: null,
    }));

    render(<ChatPage />);

    await waitFor(() => {
      expect(mockFetchTenderDataWithType).toHaveBeenCalledWith('0811-DSITC253505');
    });

    const conversation = useChatStore.getState().getCurrentConversation();
    const draft = useChatStore.getState().getConversationDraft('conv-existing');
    expect(useChatStore.getState().conversations).toHaveLength(1);
    expect(conversation?.id).toBe('conv-existing');
    expect(conversation?.title).toBe('自定义标题');
    expect(draft?.tender_data).toEqual(fetchedTenderData);
    expect(draft?.tender_type_info).toEqual({
      tender_lx: 0,
      purchase_method: 0,
      fund_lx: 1,
    });
    expect(draft?.tender_fetch).toEqual({ status: 'success' });
  });

  it('creates a new conversation and stores fetch failure state when auto-fetch fails', async () => {
    mockUseUrlParams.mockReturnValue({
      tenderno: '0811-DSITC251534',
      tenderType: 'gngk' as TenderType,
      isValid: true,
      hasParams: true,
    });
    mockFetchTenderDataWithType.mockRejectedValue(new Error('接口异常'));

    useChatStore.setState((state) => ({
      ...state,
      conversations: [],
      currentConversationId: null,
      activeTaskIds: [],
      taskMessageMap: {},
      conversationDrafts: {},
      taskSummaries: {},
      unreadConversationResults: {},
      isLoading: false,
      error: null,
      selectedTenderType: null,
    }));

    render(<ChatPage />);

    await waitFor(() => {
      expect(mockFetchTenderDataWithType).toHaveBeenCalledWith('0811-DSITC251534');
    });

    const { conversations, currentConversationId, selectedTenderType, getConversationDraft } =
      useChatStore.getState();
    expect(conversations).toHaveLength(1);
    expect(currentConversationId).toBe(conversations[0]?.id || null);
    expect(conversations[0]?.title).toBe(generateConversationTitle('0811-DSITC251534'));
    expect(selectedTenderType).toBe('gngk');
    expect(getConversationDraft(conversations[0]?.id || null)?.tender_no).toBe('0811-DSITC251534');
    expect(getConversationDraft(conversations[0]?.id || null)?.tender_fetch).toEqual({
      status: 'error',
      error: '接口异常',
    });
    expect(screen.getByText('接口异常')).toBeInTheDocument();
  });
});
