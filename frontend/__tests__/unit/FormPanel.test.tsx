import { render, screen } from '@testing-library/react';
import { FormPanel } from '@/components/chat/FormPanel';
import { useChatStore } from '@/stores/chatStore';

jest.mock('@/hooks/useHydrated', () => ({
  useHydrated: () => true,
}));

jest.mock('@/hooks/useChatSSE', () => ({
  useChatSSE: jest.fn(),
}));

const mockUseTaskHeartbeat = jest.fn();
jest.mock('@/hooks/useTaskHeartbeat', () => ({
  useTaskHeartbeat: (...args: unknown[]) => mockUseTaskHeartbeat(...args),
}));

jest.mock('@/components/forms/XjcgTenderForm', () => ({
  XjcgTenderForm: ({
    isSubmitting,
    canCancel,
  }: {
    isSubmitting?: boolean;
    canCancel?: boolean;
  }) => (
    <div
      data-testid="xjcg-form"
      data-submitting={isSubmitting ? 'true' : 'false'}
      data-can-cancel={canCancel ? 'true' : 'false'}
    >
      XjcgTenderForm
    </div>
  ),
}));

jest.mock('@/components/forms/GngkTenderForm', () => ({
  GngkTenderForm: ({
    isSubmitting,
    canCancel,
  }: {
    isSubmitting?: boolean;
    canCancel?: boolean;
  }) => (
    <div
      data-testid="gngk-form"
      data-submitting={isSubmitting ? 'true' : 'false'}
      data-can-cancel={canCancel ? 'true' : 'false'}
    >
      GngkTenderForm
    </div>
  ),
}));

describe('FormPanel', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    mockUseTaskHeartbeat.mockClear();

    useChatStore.setState((state) => ({
      ...state,
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
      activeTaskIds: ['task-queued', 'task-running'],
      taskMessageMap: {},
      concurrentTaskWarning: false,
      selectedTenderType: 'xjcg',
      isLoading: false,
      error: null,
    }));
  });

  it('keeps heartbeats alive for all active tasks even when the current conversation has no generating message', () => {
    render(<FormPanel />);

    expect(screen.getByText('XjcgTenderForm')).toBeInTheDocument();
    expect(mockUseTaskHeartbeat.mock.calls[0]?.[0]).toEqual(['task-queued', 'task-running']);
  });

  it('shows a non-blocking loading status and keeps the form in submitting state while tasks are active', () => {
    render(<FormPanel />);

    const status = screen.getByRole('status');
    expect(status).toHaveTextContent('正在生成招标文档...');
    expect(status).toHaveClass(
      'pointer-events-none',
      'absolute',
      'inset-x-0',
      'top-1/2',
      '-translate-y-1/2'
    );
    expect(screen.getByTestId('xjcg-form')).toHaveAttribute('data-submitting', 'true');
    expect(screen.queryByRole('button', { name: '取消生成' })).not.toBeInTheDocument();
  });

  it('passes cancel capability to the current form when the current conversation has a generating task', () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          messages: [
            {
              id: 'msg-1',
              conversationId: 'conv-1',
              type: 'ai',
              content: '正在生成',
              timestamp: Date.now(),
              status: 'generating',
              taskId: 'task-running',
            },
          ],
        },
      ],
      activeTaskIds: ['task-running'],
    }));

    render(<FormPanel />);

    expect(screen.getByTestId('xjcg-form')).toHaveAttribute('data-can-cancel', 'true');
  });
});
