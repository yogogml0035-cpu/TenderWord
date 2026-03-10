import { act, render, screen, waitFor } from '@testing-library/react';
import ChatPage from '@/app/chat/page';
import { useChatStore } from '@/stores/chatStore';
import { useChatStreamStore } from '@/stores/chatStreamStore';
import { useChatTaskSessionStore } from '@/stores/chatTaskSessionStore';
import type { ConversationHeartbeatData } from '@/types/api';

const mockFetchTenderData = jest.fn();
const mockSendConversationHeartbeat = jest.fn();

jest.mock('@/hooks/useHydrated', () => ({
  useHydrated: () => true,
}));

jest.mock('@/hooks/useUrlParams', () => ({
  useUrlParams: () => ({
    tenderno: null,
    tenderType: null,
    isValid: false,
    hasParams: false,
  }),
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
  fetchTenderData: (...args: unknown[]) => mockFetchTenderData(...args),
  sendConversationHeartbeat: (...args: unknown[]) => mockSendConversationHeartbeat(...args),
}));

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
              message: '正在润色',
            },
          ],
          aiText: '保留中的润色内容',
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

    mockFetchTenderData.mockReset();
    mockSendConversationHeartbeat.mockReset();
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
      expect(group?.contentMessage?.content).toBe('保留中的润色内容');
      expect(draft?.chat_input).toBe('请补充售后条款');
      expect(useChatStore.getState().activeTaskIds).toHaveLength(0);
      expect(useChatTaskSessionStore.getState().sessions['task-1']).toBeUndefined();
      expect(useChatStreamStore.getState().streams['task-1']).toBeUndefined();
    });

    expect(screen.getByTestId('chat-panel')).toBeInTheDocument();
    expect(screen.queryByText('检测到服务已重启')).not.toBeInTheDocument();
    expect(screen.queryByText('确认并重置会话')).not.toBeInTheDocument();
  });
});
