import { fireEvent, render, screen, within } from '@testing-library/react';
import { TenderTypeSidebar } from '@/components/chat/TenderTypeSidebar';
import { useChatStore } from '@/stores/chatStore';
import type { Conversation } from '@/types/chat';

jest.mock('@/hooks/useHydrated', () => ({
  useHydrated: () => true,
}));

function resetStore() {
  window.localStorage.clear();
  window.sessionStorage.clear();

  useChatStore.setState({
    conversations: [],
    currentConversationId: null,
    activeTaskIds: [],
    taskMessageMap: {},
    conversationDrafts: {},
    taskSummaries: {},
    unreadConversationResults: {},
    selectedTenderType: null,
    isLoading: false,
    error: null,
  });
}

function buildConversation(
  id: string,
  title: string,
  tenderType: Conversation['tenderType'],
  updatedAt: number
): Conversation {
  return {
    id,
    title,
    tenderType,
    createdAt: updatedAt - 1,
    updatedAt,
    messages: [],
  };
}

describe('TenderTypeSidebar', () => {
  beforeEach(() => {
    resetStore();
  });

  it('opens a type group and selects the most recently updated conversation', () => {
    useChatStore.setState({
      conversations: [
        buildConversation('conv-old', '旧会话', 'xjcg', 10),
        buildConversation('conv-new', '最新会话', 'xjcg', 50),
        buildConversation('conv-gngk', '国内公开会话', 'gngk', 30),
      ],
      currentConversationId: 'conv-old',
    });

    render(<TenderTypeSidebar />);

    fireEvent.click(screen.getByTestId('tender-type-button-xjcg'));

    expect(useChatStore.getState().currentConversationId).toBe('conv-new');
    expect(screen.getByTestId('tender-type-button-xjcg')).toHaveAttribute(
      'aria-expanded',
      'true'
    );
    expect(screen.getByText('最新会话')).toBeInTheDocument();
  });

  it('creates a conversation automatically when the clicked type has no history', () => {
    render(<TenderTypeSidebar />);

    fireEvent.click(screen.getByTestId('tender-type-button-gngk'));

    const state = useChatStore.getState();
    expect(state.selectedTenderType).toBe('gngk');
    expect(state.conversations).toHaveLength(1);
    expect(state.conversations[0]?.tenderType).toBe('gngk');
    expect(state.currentConversationId).toBe(state.conversations[0]?.id || null);
    expect(screen.getByText('新对话')).toBeInTheDocument();
  });

  it('renders and creates conversations for gjgk', () => {
    render(<TenderTypeSidebar />);

    expect(screen.getByText('国际公开')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('tender-type-button-gjgk'));

    const state = useChatStore.getState();
    expect(state.selectedTenderType).toBe('gjgk');
    expect(state.conversations[0]?.tenderType).toBe('gjgk');
  });

  it('shows all conversations for the expanded type instead of truncating to five items', () => {
    useChatStore.setState({
      conversations: Array.from({ length: 6 }, (_, index) =>
        buildConversation(
          `conv-${index + 1}`,
          `询价会话-${index + 1}`,
          'xjcg',
          100 - index
        )
      ),
    });

    render(<TenderTypeSidebar />);

    fireEvent.click(screen.getByTestId('tender-type-button-xjcg'));

    for (let index = 1; index <= 6; index += 1) {
      expect(screen.getByText(`询价会话-${index}`)).toBeInTheDocument();
    }
  });

  it('collapses the previous type group when another type is selected', () => {
    useChatStore.setState({
      conversations: [
        buildConversation('conv-xjcg', '询价会话-1', 'xjcg', 100),
        buildConversation('conv-gngk', '公开会话-1', 'gngk', 90),
      ],
    });

    render(<TenderTypeSidebar />);

    fireEvent.click(screen.getByTestId('tender-type-button-xjcg'));
    expect(screen.getByText('询价会话-1')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('tender-type-button-gngk'));

    expect(screen.getByTestId('tender-type-button-xjcg')).toHaveAttribute(
      'aria-expanded',
      'false'
    );
    expect(screen.getByTestId('tender-type-button-gngk')).toHaveAttribute('aria-expanded', 'true');
    expect(screen.queryByText('询价会话-1')).not.toBeInTheDocument();
    expect(screen.getByText('公开会话-1')).toBeInTheDocument();
  });

  it('supports inline new chat, rename, and delete actions inside the expanded group', () => {
    useChatStore.setState({
      conversations: [buildConversation('conv-action', '可操作会话', 'xjcg', 10)],
      currentConversationId: 'conv-action',
      selectedTenderType: 'xjcg',
    });

    render(<TenderTypeSidebar />);

    fireEvent.click(screen.getByTestId('tender-type-new-chat-xjcg'));

    expect(useChatStore.getState().conversations).toHaveLength(2);
    expect(screen.getByText('新对话')).toBeInTheDocument();

    const conversationRow = screen.getByTestId('conversation-item-conv-action');
    fireEvent.click(within(conversationRow).getByRole('button', { name: '更多操作' }));
    fireEvent.click(screen.getByRole('button', { name: '重命名' }));

    const input = screen.getByDisplayValue('可操作会话');
    fireEvent.change(input, { target: { value: '已重命名会话' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    expect(
      useChatStore.getState().conversations.find((item) => item.id === 'conv-action')?.title
    ).toBe('已重命名会话');
    expect(screen.getByText('已重命名会话')).toBeInTheDocument();

    fireEvent.click(
      within(screen.getByTestId('conversation-item-conv-action')).getByRole('button', {
        name: '更多操作',
      })
    );
    fireEvent.click(screen.getByRole('button', { name: '删除' }));

    expect(
      useChatStore.getState().conversations.find((item) => item.id === 'conv-action')
    ).toBeUndefined();
    expect(screen.queryByText('已重命名会话')).not.toBeInTheDocument();
  });
});
