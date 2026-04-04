import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ChatPanel } from '@/components/chat/ChatPanel';
import { cancelTask, createEditTask, streamUserMessage, uploadFile } from '@/lib/api';
import { useChatStore } from '@/stores/chatStore';
import { useChatStreamStore } from '@/stores/chatStreamStore';
import type { UserStreamEvent } from '@/types/api';
import type { Message } from '@/types/chat';

jest.mock('@/lib/api', () => {
  const actual = jest.requireActual('@/lib/api');
  return {
    ...actual,
    cancelTask: jest.fn(),
    createEditTask: jest.fn(),
    downloadFile: jest.fn(),
    streamUserMessage: jest.fn(),
    uploadFile: jest.fn(),
  };
});

jest.mock('@/hooks/useHydrated', () => ({
  useHydrated: () => true,
}));

jest.mock('@/components/chat/MessageList', () => ({
  MessageList: ({
    messages,
    emptyState,
    onRetry,
  }: {
    messages: Array<unknown>;
    emptyState?: unknown;
    onRetry?: (message: Message) => void;
  }) => (
    <div data-testid="message-list">
      {messages.length === 0 ? (
        emptyState ? (
          <div data-testid="custom-empty">custom-empty</div>
        ) : (
          <div data-testid="default-empty">default-empty</div>
        )
      ) : (
        <div data-testid="message-count">{messages.length}</div>
      )}
      {onRetry && messages.length > 0 && (
        <button
          type="button"
          data-testid="retry-message-button"
          onClick={() => onRetry(messages[0] as Message)}
        >
          retry message
        </button>
      )}
    </div>
  ),
}));

jest.mock('@/components/chat/ChatInput', () => ({
  ChatInput: ({
    value,
    disabled,
    loading,
    placeholder,
    selectedModel,
    inputMode,
    editFile,
    sendDisabled,
    noticeMessage,
    onModelChange,
    onCancel,
    onSend,
    onEditFileSelect,
    onEditFileRemove,
  }: {
    value?: string;
    disabled?: boolean;
    loading?: boolean;
    placeholder?: string;
    selectedModel?: string;
    inputMode?: 'normal' | 'edit';
    editFile?: { original_name?: string } | null;
    sendDisabled?: boolean;
    noticeMessage?: string | null;
    onModelChange?: (model: string) => void;
    onCancel?: () => void;
    onSend?: (message: string) => void;
    onEditFileSelect?: (file: File) => void | Promise<void>;
    onEditFileRemove?: () => void;
  }) => (
    <div
      data-testid="chat-input"
      data-disabled={disabled ? 'true' : 'false'}
      data-loading={loading ? 'true' : 'false'}
      data-placeholder={placeholder || ''}
      data-model={selectedModel || ''}
      data-input-mode={inputMode || 'normal'}
      data-send-disabled={sendDisabled ? 'true' : 'false'}
      data-notice={noticeMessage || ''}
      data-edit-file={editFile?.original_name || ''}
    >
      <button type="button" data-testid="change-model-button" onClick={() => onModelChange?.('qwen')}>
        change model
      </button>
      <button
        type="button"
        data-testid="send-current-input-button"
        onClick={() => onSend?.(value || 'default message')}
      >
        send current input
      </button>
      <button type="button" data-testid="cancel-chat-button" onClick={() => onCancel?.()}>
        cancel chat
      </button>
      <button
        type="button"
        data-testid="select-edit-file-button"
        onClick={() =>
          onEditFileSelect?.(
            new File(['content'], 'edit.docx', {
              type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            })
          )
        }
      >
        select edit file
      </button>
      <button type="button" data-testid="remove-edit-file-button" onClick={() => onEditFileRemove?.()}>
        remove edit file
      </button>
    </div>
  ),
}));

const mockStreamUserMessage = streamUserMessage as jest.MockedFunction<typeof streamUserMessage>;
const mockCancelTask = cancelTask as jest.MockedFunction<typeof cancelTask>;
const mockCreateEditTask = createEditTask as jest.MockedFunction<typeof createEditTask>;
const mockUploadFile = uploadFile as jest.MockedFunction<typeof uploadFile>;

function mockUserStream(events: UserStreamEvent[], terminalError?: unknown) {
  mockStreamUserMessage.mockImplementationOnce(async (_payload, options = {}) => {
    for (const event of events) {
      await options.onEvent?.(event);
    }
    if (terminalError) {
      throw terminalError;
    }
  });
}

describe('ChatPanel', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    mockStreamUserMessage.mockReset();
    mockCancelTask.mockReset();
    mockCreateEditTask.mockReset();
    mockUploadFile.mockReset();
    mockCancelTask.mockResolvedValue({
      success: true,
      task_id: 'task-1',
      message: '任务已取消',
      was_running: true,
    });
    mockUploadFile.mockResolvedValue({
      file_path: 'D:/UploadFiles/edit.docx',
      file_name: 'edit.docx',
      original_name: 'edit.docx',
      size: 128,
      upload_time: new Date().toISOString(),
    });

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
          currentTaskId: 'task-1',
        },
      ],
      currentConversationId: 'conv-1',
      activeTaskIds: ['task-1'],
      taskMessageMap: {},
      conversationDrafts: {},
      taskSummaries: {
        'task-1': {
          task_id: 'task-1',
          status: 'queued',
          waiting_count: 2,
          updated_at: Date.now(),
        },
      },
      selectedTenderType: 'xjcg',
      isLoading: false,
      error: null,
    }));
    useChatStreamStore.setState({ streams: {} });
  });

  it('suppresses the default empty state while queued without showing a top status bar', () => {
    render(<ChatPanel />);

    expect(
      screen.queryByText('排队中，轮到当前任务后将开始显示进度日志')
    ).not.toBeInTheDocument();
    expect(screen.getByTestId('custom-empty')).toBeInTheDocument();
    expect(screen.queryByTestId('default-empty')).not.toBeInTheDocument();
    expect(screen.getByTestId('chat-input')).toHaveAttribute('data-model', 'deepseek');
  });

  it('does not show queue status bar for running conversation', () => {
    useChatStore.setState((state) => ({
      ...state,
      taskSummaries: {
        'task-1': {
          task_id: 'task-1',
          status: 'running',
          updated_at: Date.now(),
        },
      },
    }));

    render(<ChatPanel />);

    expect(
      screen.queryByText('排队中，轮到当前任务后将开始显示进度日志')
    ).not.toBeInTheDocument();
  });

  it('shows the registered tender type label for gjgk conversations', () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          tenderType: 'gjgk',
          currentTaskId: undefined,
        },
      ],
      activeTaskIds: [],
      taskSummaries: {},
      selectedTenderType: 'gjgk',
    }));

    render(<ChatPanel />);

    expect(screen.getByText('国际公开')).toBeInTheDocument();
  });

  it('suppresses the default empty state while starting without showing a top status bar', () => {
    useChatStore.setState((state) => ({
      ...state,
      taskSummaries: {
        'task-1': {
          task_id: 'task-1',
          status: 'queued',
          waiting_count: 0,
          updated_at: Date.now(),
        },
      },
    }));

    render(<ChatPanel />);

    expect(screen.queryByText('排队中，轮到当前任务后将开始显示进度日志')).not.toBeInTheDocument();
    expect(screen.queryByText('正在启动任务，稍后将显示进度日志')).not.toBeInTheDocument();
    expect(screen.getByTestId('custom-empty')).toBeInTheDocument();
  });

  it('uses the conversation draft model when present', () => {
    useChatStore.setState((state) => ({
      ...state,
      conversationDrafts: {
        'conv-1': {
          model: 'doubao',
        },
      },
    }));

    render(<ChatPanel />);

    expect(screen.getByTestId('chat-input')).toHaveAttribute('data-model', 'doubao');
  });

  it('updates the current conversation draft when model changes from chat input', () => {
    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('change-model-button'));

    expect(useChatStore.getState().getConversationDraft('conv-1')?.model).toBe('qwen');
  });

  it('does not expose a rewrite toggle in chat input', () => {
    render(<ChatPanel />);

    expect(screen.queryByTestId('toggle-rewrite-button')).not.toBeInTheDocument();
    expect(screen.getByTestId('chat-input')).toHaveAttribute('data-placeholder', '回复生成中，请稍候...');
  });

  it('uploads a file and switches the draft into edit mode', async () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          currentTaskId: undefined,
        },
      ],
      activeTaskIds: [],
      taskSummaries: {},
    }));

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('select-edit-file-button'));

    await waitFor(() => {
      expect(mockUploadFile).toHaveBeenCalledTimes(1);
      const draft = useChatStore.getState().getConversationDraft('conv-1');
      expect(draft?.input_mode).toBe('edit');
      expect(draft?.edit_file?.original_name).toBe('edit.docx');
    });
  });

  it('blocks edit send when required context is incomplete', () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          currentTaskId: undefined,
        },
      ],
      activeTaskIds: [],
      taskSummaries: {},
      conversationDrafts: {
        'conv-1': {
          chat_input: '请补充质保条款',
          input_mode: 'edit',
          edit_file: {
            id: 'file-1',
            file_path: 'D:/UploadFiles/edit.docx',
            file_name: 'edit.docx',
            original_name: 'edit.docx',
            size: 128,
            upload_time: new Date().toISOString(),
          },
          tender_lx: 0,
          fund_lx: 1,
        },
      },
    }));

    render(<ChatPanel />);

    expect(screen.getByTestId('chat-input')).toHaveAttribute('data-send-disabled', 'true');
    expect(screen.getByTestId('chat-input')).toHaveAttribute('data-notice', '请先补全当前页面的插入锚点');

    fireEvent.click(screen.getByTestId('send-current-input-button'));
    expect(mockCreateEditTask).not.toHaveBeenCalled();
  });

  it('creates an edit task directly without using the user stream route', async () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          currentTaskId: undefined,
        },
      ],
      activeTaskIds: [],
      taskSummaries: {},
      conversationDrafts: {
        'conv-1': {
          chat_input: '请把交付日期改成合同签订后 30 天内',
          input_mode: 'edit',
          edit_file: {
            id: 'file-1',
            file_path: 'D:/UploadFiles/edit.docx',
            file_name: 'edit.docx',
            original_name: 'edit.docx',
            size: 128,
            upload_time: new Date().toISOString(),
          },
          tender_lx: 0,
          fund_lx: 1,
          insertion_config: {
            before_text: '第三章 采购需求',
            after_text: '第四章 响应文件有关格式',
          },
          tender_data: {
            project_name: '示例项目',
            project_number: 'ZBGG-2026-001',
            project_content: '原始内容',
            bzj_rule: '',
            buyer_name: '示例单位',
            project_zbr_xbr: '',
            zbr_xbr_tel: '',
            zbr_pinyin: '',
            shell_start_date: '',
            shell_end_date: '',
            submit_date: '',
            platform: '',
            service_fee: '',
            tender_lx: 0,
            fund_source_lx: 1,
          },
        },
      },
    }));
    mockCreateEditTask.mockResolvedValue({
      task_id: 'task-edit',
      task_kind: 'edit',
      status: 'queued',
      queue_position: 0,
      waiting_count: 0,
    });

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('send-current-input-button'));

    await waitFor(() => {
      expect(mockCreateEditTask).toHaveBeenCalledTimes(1);
      expect(mockStreamUserMessage).not.toHaveBeenCalled();
      const conversation = useChatStore.getState().conversations[0];
      const draft = useChatStore.getState().getConversationDraft('conv-1');
      expect(conversation.currentTaskId).toBe('task-edit');
      expect(draft?.pending_edit_task_id).toBe('task-edit');
      expect(conversation.messages[0]).toMatchObject({
        type: 'user',
        metadata: {
          chatKind: 'edit',
        },
      });
      expect(conversation.messages[1]).toMatchObject({
        type: 'ai',
        content: '正在创建文件修改任务',
        metadata: {
          chatKind: 'edit',
        },
      });
    });

    expect(mockCreateEditTask).toHaveBeenCalledWith({
      conversation_id: 'conv-1',
      form_type: 'xjcg_tender',
      model: 'deepseek',
      edit_prompt: '请把交付日期改成合同签订后 30 天内',
      file_path: 'D:/UploadFiles/edit.docx',
      insertion_config: {
        before_text: '第三章 采购需求',
        after_text: '第四章 响应文件有关格式',
      },
      tender_lx: 0,
      fund_source_lx: 1,
      tender_data_snapshot: expect.objectContaining({
        project_name: '示例项目',
      }),
    });
  });

  it('keeps the latest edit output as the default file for the next edit', async () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          currentTaskId: undefined,
          messages: [
            {
              id: 'msg-download',
              conversationId: 'conv-1',
              type: 'ai',
              content: 'latest-edit.docx',
              timestamp: Date.now(),
              status: 'completed',
              taskId: 'task-edit-finished',
              metadata: {
                messageKind: 'task-download',
                taskKind: 'edit',
                outputFile: 'D:/UploadFiles/latest-edit.docx',
                fileName: 'latest-edit.docx',
              },
            },
          ],
        },
      ],
      activeTaskIds: [],
      taskMessageMap: {
        'task-edit-finished': {
          downloadMessageId: 'msg-download',
        },
      },
      taskSummaries: {
        'task-edit-finished': {
          task_id: 'task-edit-finished',
          task_kind: 'edit',
          status: 'completed',
          updated_at: Date.now(),
        },
      },
      conversationDrafts: {
        'conv-1': {
          input_mode: 'edit',
          pending_edit_prompt: '请继续修改',
          pending_edit_task_id: 'task-edit-finished',
          edit_file: {
            id: 'old-file',
            file_path: 'D:/UploadFiles/old-edit.docx',
            file_name: 'old-edit.docx',
            original_name: 'old-edit.docx',
            size: 256,
            upload_time: new Date().toISOString(),
          },
        },
      },
    }));

    render(<ChatPanel />);

    await waitFor(() => {
      const draft = useChatStore.getState().getConversationDraft('conv-1');
      expect(draft?.pending_edit_task_id).toBeUndefined();
      expect(draft?.input_mode).toBe('edit');
      expect(draft?.edit_file?.file_path).toBe('D:/UploadFiles/latest-edit.docx');
      expect(draft?.edit_file?.original_name).toBe('latest-edit.docx');
    });
  });

  it('retries failed ai message in place instead of appending a new bubble', async () => {
    const failedMessage: Message = {
      id: 'msg-ai-failed',
      conversationId: 'conv-1',
      type: 'ai',
      content: '旧的失败内容',
      timestamp: Date.now(),
      status: 'error',
      metadata: {
        chatKind: 'normal',
        chatPrompt: '请重试',
        chatModel: 'qwen',
      },
    };

    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          currentTaskId: undefined,
          messages: [failedMessage],
        },
      ],
      activeTaskIds: [],
      taskSummaries: {},
    }));

    mockUserStream([
      { event: 'route', data: { route: 'reply' } },
      { event: 'done', data: { content: '重试成功内容' } },
    ]);

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('retry-message-button'));

    await waitFor(() => {
      const conversation = useChatStore.getState().conversations[0];
      expect(conversation.messages).toHaveLength(1);
      expect(conversation.messages[0].id).toBe('msg-ai-failed');
      expect(conversation.messages[0].status).toBe('completed');
      expect(conversation.messages[0].content).toBe('重试成功内容');
    });

    expect(mockStreamUserMessage).toHaveBeenCalledTimes(1);
  });

  it('auto routes rewrite-like input in normal mode to rewrite task flow', async () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          currentTaskId: undefined,
        },
      ],
      activeTaskIds: [],
      taskSummaries: {},
      conversationDrafts: {
        'conv-1': {
          chat_input: '请帮我修改这一段内容',
        },
      },
    }));

    mockUserStream([
      { event: 'route', data: { route: 'rewrite' } },
      {
        event: 'task_accepted',
        data: {
          task_id: 'task-rewrite',
          task_kind: 'rewrite',
          status: 'queued',
          queue_position: 0,
          waiting_count: 0,
        },
      },
    ]);

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('send-current-input-button'));

    await waitFor(() => {
      const conversation = useChatStore.getState().conversations[0];
      const draft = useChatStore.getState().getConversationDraft('conv-1');
      expect(conversation.currentTaskId).toBe('task-rewrite');
      expect(draft?.pending_rewrite_task_id).toBe('task-rewrite');
      expect(conversation.messages).toHaveLength(2);
      expect(conversation.messages[0].metadata?.chatKind).toBe('rewrite');
      expect(conversation.messages[1]).toMatchObject({
        type: 'ai',
        content: '正在创建修改重写任务',
        status: 'completed',
        metadata: {
          chatKind: 'rewrite',
        },
      });
    });

    expect(mockStreamUserMessage).toHaveBeenCalledTimes(1);
    expect(mockStreamUserMessage.mock.calls[0]?.[0]).toMatchObject({
      conversation_id: 'conv-1',
      model: 'deepseek',
      messages: [{ role: 'user', content: '请帮我修改这一段内容' }],
    });
  });

  it('keeps ordinary chat on the streaming path without creating a task', async () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          currentTaskId: undefined,
        },
      ],
      activeTaskIds: [],
      taskSummaries: {},
      conversationDrafts: {
        'conv-1': {
          chat_input: '你好',
        },
      },
    }));

    mockUserStream([
      { event: 'route', data: { route: 'reply' } },
      { event: 'done', data: { content: '你好，请问有什么可以帮你？' } },
    ]);

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('send-current-input-button'));

    await waitFor(() => {
      const conversation = useChatStore.getState().conversations[0];
      expect(conversation.currentTaskId).toBeUndefined();
      expect(conversation.messages).toHaveLength(2);
      expect(conversation.messages[1].type).toBe('ai');
      expect(conversation.messages[1].status).toBe('completed');
    });
  });

  it('excludes task-notice ai bubbles from normal chat context', async () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          currentTaskId: undefined,
          messages: [
            {
              id: 'msg-task-notice',
              conversationId: 'conv-1',
              type: 'ai',
              content: '正在创建生成招标文件任务',
              timestamp: Date.now(),
              status: 'completed',
              metadata: {
                chatKind: 'task-notice',
              },
            },
          ],
        },
      ],
      activeTaskIds: [],
      taskSummaries: {},
      conversationDrafts: {
        'conv-1': {
          chat_input: '继续帮我解释一下',
        },
      },
    }));

    mockUserStream([
      { event: 'route', data: { route: 'reply' } },
      { event: 'done', data: { content: '好的，我继续说明。' } },
    ]);

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('send-current-input-button'));

    await waitFor(() => {
      expect(mockStreamUserMessage).toHaveBeenCalledTimes(1);
    });

    expect(mockStreamUserMessage.mock.calls[0]?.[0].messages).toEqual([
      { role: 'user', content: '继续帮我解释一下' },
    ]);
  });

  it('removes the rewrite placeholder bubble when the rewrite stream fails before task acceptance', async () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          currentTaskId: undefined,
        },
      ],
      activeTaskIds: [],
      taskSummaries: {},
      conversationDrafts: {
        'conv-1': {
          chat_input: '请帮我修改这一段内容',
        },
      },
    }));

    mockUserStream([
      { event: 'route', data: { route: 'rewrite' } },
      {
        event: 'error',
        data: {
          message: '修改任务创建失败',
        },
      },
    ]);

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('send-current-input-button'));

    await waitFor(() => {
      const conversation = useChatStore.getState().conversations[0];
      expect(conversation.currentTaskId).toBeUndefined();
      expect(conversation.messages).toHaveLength(2);
      expect(conversation.messages[0]).toMatchObject({
        type: 'user',
        metadata: {
          chatKind: 'rewrite',
        },
      });
      expect(conversation.messages[1]).toMatchObject({
        type: 'system',
        content: '修改任务创建失败',
        status: 'completed',
      });
      expect(conversation.messages.find((message) => message.content === '正在创建修改重写任务')).toBeUndefined();
    });
  });

  it('cancels an active normal chat stream through the shared AbortSignal path', async () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          currentTaskId: undefined,
        },
      ],
      activeTaskIds: [],
      taskSummaries: {},
      conversationDrafts: {
        'conv-1': {
          chat_input: '帮我写一段说明',
        },
      },
    }));

    mockStreamUserMessage.mockImplementationOnce(
      async (_payload, options = {}) =>
        new Promise<void>((_resolve, reject) => {
          void (async () => {
            await options.onEvent?.({ event: 'route', data: { route: 'reply' } });
            await options.onEvent?.({ event: 'chunk', data: { content: '正在生成中' } });
          })();
          options.signal?.addEventListener(
            'abort',
            () => reject(new DOMException('Aborted', 'AbortError')),
            { once: true }
          );
        })
    );

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('send-current-input-button'));

    await waitFor(() => {
      const conversation = useChatStore.getState().conversations[0];
      expect(conversation.messages[1]).toMatchObject({
        type: 'ai',
        status: 'generating',
        content: '正在生成中',
      });
    });

    fireEvent.click(screen.getByTestId('cancel-chat-button'));

    await waitFor(() => {
      const conversation = useChatStore.getState().conversations[0];
      expect(conversation.messages[1]).toMatchObject({
        type: 'ai',
        status: 'cancelled',
        content: '正在生成中',
      });
    });
  });
});
