import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ChatPanel } from '@/components/chat/ChatPanel';
import {
  cancelTask,
  createCommentSupplementTask,
  streamAgentRun,
  uploadFile,
} from '@/lib/api';
import { useChatStore } from '@/stores/chatStore';
import { useChatStreamStore } from '@/stores/chatStreamStore';
import type { AgentRunEvent, AgentSkill } from '@/types/api';
import type { Message } from '@/types/chat';

jest.mock('@/lib/api', () => {
  const actual = jest.requireActual('@/lib/api');
  return {
    ...actual,
    cancelTask: jest.fn(),
    createCommentSupplementTask: jest.fn(),
    downloadFile: jest.fn(),
    streamAgentRun: jest.fn(),
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
    onCommentSupplement,
    onRetry,
    commentSupplementDisabled,
  }: {
    messages: Message[];
    emptyState?: unknown;
    onCommentSupplement?: (message: Message) => void;
    onRetry?: (message: Message) => void;
    commentSupplementDisabled?: boolean;
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
      {onCommentSupplement && messages.length > 0 && (
        <button
          type="button"
          data-testid="comment-supplement-button"
          disabled={commentSupplementDisabled}
          onClick={() => onCommentSupplement(messages[messages.length - 1])}
        >
          supplement comments
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
    rewriteFile,
    selectedSkills,
    sendDisabled,
    noticeMessage,
    onModelChange,
    onCancel,
    onSend,
    onRewriteFileSelect,
    onRewriteFileRemove,
    onSelectedSkillsChange,
  }: {
    value?: string;
    disabled?: boolean;
    loading?: boolean;
    placeholder?: string;
    selectedModel?: string;
    rewriteFile?: { original_name?: string } | null;
    selectedSkills?: AgentSkill[];
    sendDisabled?: boolean;
    noticeMessage?: string | null;
    onModelChange?: (model: string) => void;
    onCancel?: () => void;
    onSend?: (message: string) => boolean | void | Promise<boolean | void>;
    onRewriteFileSelect?: (file: File) => void | Promise<void>;
    onRewriteFileRemove?: () => void;
    onSelectedSkillsChange?: (skills: AgentSkill[]) => void;
  }) => (
    <div
      data-testid="chat-input"
      data-disabled={disabled ? 'true' : 'false'}
      data-loading={loading ? 'true' : 'false'}
      data-placeholder={placeholder || ''}
      data-model={selectedModel || ''}
      data-send-disabled={sendDisabled ? 'true' : 'false'}
      data-notice={noticeMessage || ''}
      data-rewrite-file={rewriteFile?.original_name || ''}
      data-selected-skills={selectedSkills?.join(',') || ''}
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
        data-testid="select-rewrite-file-button"
        onClick={() =>
          onRewriteFileSelect?.(
            new File(['content'], 'rewrite.docx', {
              type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            })
          )
        }
      >
        select rewrite file
      </button>
      <button type="button" data-testid="remove-rewrite-file-button" onClick={() => onRewriteFileRemove?.()}>
        remove rewrite file
      </button>
      <button
        type="button"
        data-testid="select-rewrite-skill-button"
        onClick={() => onSelectedSkillsChange?.(['rewrite'])}
      >
        select rewrite skill
      </button>
      <button
        type="button"
        data-testid="clear-selected-skills-button"
        onClick={() => onSelectedSkillsChange?.([])}
      >
        clear selected skills
      </button>
    </div>
  ),
}));

const mockStreamAgentRun = streamAgentRun as jest.MockedFunction<typeof streamAgentRun>;
const mockCancelTask = cancelTask as jest.MockedFunction<typeof cancelTask>;
const mockCreateCommentSupplementTask = createCommentSupplementTask as jest.MockedFunction<
  typeof createCommentSupplementTask
>;
const mockUploadFile = uploadFile as jest.MockedFunction<typeof uploadFile>;

function createDeferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });

  return { promise, resolve, reject };
}

function mockAgentRunStream(events: AgentRunEvent[], terminalError?: unknown) {
  mockStreamAgentRun.mockImplementationOnce(async (_payload, options = {}) => {
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
    mockStreamAgentRun.mockReset();
    mockCancelTask.mockReset();
    mockCreateCommentSupplementTask.mockReset();
    mockUploadFile.mockReset();
    mockCancelTask.mockResolvedValue({
      success: true,
      task_id: 'task-1',
      message: '任务已取消',
      was_running: true,
    });
    mockUploadFile.mockResolvedValue({
      file_path: 'D:/UploadFiles/rewrite.docx',
      file_name: 'rewrite.docx',
      original_name: 'rewrite.docx',
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

  it('sends selected_skills through agent run and clears the draft selection after send', async () => {
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
          chat_input: '请帮我改写这一段内容',
        },
      },
    }));

    mockAgentRunStream([]);

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('select-rewrite-skill-button'));
    expect(screen.getByTestId('chat-input')).toHaveAttribute('data-selected-skills', 'rewrite');

    fireEvent.click(screen.getByTestId('send-current-input-button'));

    await waitFor(() => {
      expect(mockStreamAgentRun).toHaveBeenCalledTimes(1);
    });

    expect(mockStreamAgentRun.mock.calls[0]?.[0]).toMatchObject({
      conversation_id: 'conv-1',
      message: '请帮我改写这一段内容',
      selected_skills: ['rewrite'],
    });
    expect(useChatStore.getState().getConversationDraft('conv-1')?.selected_skills).toBeUndefined();
  });

  it('uploads a file and switches the draft into rewrite file chain', async () => {
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

    fireEvent.click(screen.getByTestId('select-rewrite-file-button'));

    await waitFor(() => {
      expect(mockUploadFile).toHaveBeenCalledTimes(1);
      expect(mockUploadFile).toHaveBeenCalledWith(expect.any(File), 'rewrite_source');
      const draft = useChatStore.getState().getConversationDraft('conv-1');
      expect(draft?.rewrite_file?.original_name).toBe('rewrite.docx');
      expect(draft?.selected_skills).toEqual(['rewrite']);
    });
  });

  it('routes incomplete rewrite context through agent run and shows the follow-up message', async () => {
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

          rewrite_file: {
            id: 'file-1',
            file_path: 'D:/UploadFiles/rewrite.docx',
            file_name: 'rewrite.docx',
            original_name: 'rewrite.docx',
            size: 128,
            upload_time: new Date().toISOString(),
          },
          tender_lx: 0,
          fund_lx: 1,
        },
      },
    }));

    mockAgentRunStream([
      {
        event: 'needs_input',
        data: {
          run_id: 'run-rewrite-needs-anchor',
          message: '请先补全当前页面的插入锚点',
          selected_skill: 'rewrite',
          missing_requirements: ['rewrite_context.insertion_config'],
        },
      },
    ]);

    render(<ChatPanel />);

    expect(screen.getByTestId('chat-input')).toHaveAttribute('data-send-disabled', 'false');
    expect(screen.getByTestId('chat-input')).toHaveAttribute('data-notice', '');

    fireEvent.click(screen.getByTestId('send-current-input-button'));

    await waitFor(() => {
      expect(mockStreamAgentRun).toHaveBeenCalledTimes(1);
    });

    expect(mockStreamAgentRun.mock.calls[0]?.[0]).toMatchObject({
      conversation_id: 'conv-1',
      message: '请补充质保条款',
      selected_skills: ['rewrite'],
      context_snapshot: {
        rewrite_available: false,
        uploaded_files: [
          {
            file_path: 'D:/UploadFiles/rewrite.docx',
            file_name: 'rewrite.docx',
          },
        ],
        rewrite_context: {
          form_type: 'xjcg_tender',
          tender_lx: 0,
          fund_source_lx: 1,
        },
      },
    });
    expect(screen.getByTestId('chat-input')).toHaveAttribute('data-notice', '');
    const conversation = useChatStore.getState().conversations[0];
    expect(conversation.currentTaskId).toBeUndefined();
    expect(conversation.messages.find((message) => message.content === '请先补全当前页面的插入锚点')).toMatchObject({
      type: 'ai',
      content: '请先补全当前页面的插入锚点',
      status: 'completed',
    });
  });

  it('keeps uploaded rewrite context when rewrite is explicitly selected', async () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          currentTaskId: undefined,
          tenderType: 'xjcg',
        },
      ],
      activeTaskIds: [],
      taskSummaries: {},
      conversationDrafts: {
        'conv-1': {
          chat_input: '请把交付日期改成合同签订后 30 天内',

          selected_skills: ['rewrite'],
          rewrite_file: {
            id: 'file-1',
            file_path: 'D:/UploadFiles/rewrite.docx',
            file_name: 'rewrite.docx',
            original_name: 'rewrite.docx',
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

    mockAgentRunStream([]);

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('send-current-input-button'));

    await waitFor(() => {
      expect(mockStreamAgentRun).toHaveBeenCalledTimes(1);
    });

    expect(mockStreamAgentRun.mock.calls[0]?.[0]).toMatchObject({
      conversation_id: 'conv-1',
      message: '请把交付日期改成合同签订后 30 天内',
      selected_skills: ['rewrite'],
      context_snapshot: {
        rewrite_available: false,
        uploaded_files: [
          {
            file_path: 'D:/UploadFiles/rewrite.docx',
            file_name: 'rewrite.docx',
          },
        ],
        rewrite_context: {
          form_type: 'xjcg_tender',
          insertion_config: {
            before_text: '第三章 采购需求',
            after_text: '第四章 响应文件有关格式',
          },
          tender_lx: 0,
          fund_source_lx: 1,
          tender_data_snapshot: expect.objectContaining({
            project_name: '示例项目',
            fund_source_lx: 1,
          }),
        },
      },
    });
  });

  it('routes uploaded file rewrite requests through agent run and tracks the accepted rewrite task', async () => {
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

          generation_mode: 'agent',
          comment_generation_mode: 'off',
          rewrite_file: {
            id: 'file-1',
            file_path: 'D:/UploadFiles/rewrite.docx',
            file_name: 'rewrite.docx',
            original_name: 'rewrite.docx',
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

    mockAgentRunStream([
      {
        event: 'run_started',
        data: {
          run_id: 'run-rewrite-implicit',
          conversation_id: 'conv-1',
          model: 'deepseek',
          runtime: 'fake',
          selected_skills: ['rewrite'],
        },
      },
      {
        event: 'thinking_stage',
        data: {
          run_id: 'run-rewrite-implicit',
          stage: 'guard',
          label: '检查上下文',
          status: 'completed',
          summary: '检测到当前会话已有上传文件和完整 rewrite 上下文。',
          selected_skill: 'rewrite',
          guard_result: 'passed',
        },
      },
      {
        event: 'task_accepted',
        data: {
          run_id: 'run-rewrite-implicit',
          task_id: 'task-rewrite',
          task_kind: 'rewrite',
          status: 'queued',
          queue_position: 0,
          waiting_count: 0,
        },
      },
      {
        event: 'done',
        data: {
          run_id: 'run-rewrite-implicit',
          message: '已为你创建 rewrite 任务。',
          task_id: 'task-rewrite',
          selected_skill: 'rewrite',
        },
      },
    ]);

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('send-current-input-button'));

    await waitFor(() => {
      expect(mockStreamAgentRun).toHaveBeenCalledTimes(1);
      const conversation = useChatStore.getState().conversations[0];
      const draft = useChatStore.getState().getConversationDraft('conv-1');
      const taskGroup = useChatStore.getState().findTaskMessageGroup('task-rewrite');
      const thinkingMessage = conversation.messages.find((message) => message.metadata?.agentThinking);
      expect(conversation.currentTaskId).toBe('task-rewrite');
      expect(draft?.pending_rewrite_task_id).toBe('task-rewrite');
      expect(conversation.messages[0]).toMatchObject({
        type: 'user',
        metadata: {
          chatKind: 'rewrite',
        },
      });
      expect(thinkingMessage).toBeUndefined();
      expect(taskGroup?.logMessage).toMatchObject({
        taskId: 'task-rewrite',
        status: 'generating',
        metadata: {
          messageKind: 'task-log',
          taskKind: 'rewrite',
        },
      });
      expect(taskGroup?.contentMessage).toBeUndefined();
    });

    const rewritePayload = mockStreamAgentRun.mock.calls[0]?.[0];
    expect(rewritePayload).toEqual({
      conversation_id: 'conv-1',
      model: 'deepseek',
      message: '请把交付日期改成合同签订后 30 天内',
      selected_skills: ['rewrite'],
      context_snapshot: {
        rewrite_available: false,
        uploaded_files: [
          {
            file_path: 'D:/UploadFiles/rewrite.docx',
            file_name: 'rewrite.docx',
          },
        ],
        rewrite_context: {
          form_type: 'xjcg_tender',
          insertion_config: {
            before_text: '第三章 采购需求',
            after_text: '第四章 响应文件有关格式',
          },
          tender_lx: 0,
          fund_source_lx: 1,
          tender_data_snapshot: expect.objectContaining({
            project_name: '示例项目',
          }),
        },
      },
    });
  });

  it('sends the mapped gngk rewrite form type through agent run context', async () => {
    useChatStore.setState((state) => ({
      ...state,
      conversations: [
        {
          ...state.conversations[0],
          tenderType: 'gngk',
          currentTaskId: undefined,
        },
      ],
      selectedTenderType: 'gngk',
      activeTaskIds: [],
      taskSummaries: {},
      conversationDrafts: {
        'conv-1': {
          chat_input: '请补充技术要求',

          rewrite_file: {
            id: 'file-1',
            file_path: 'D:/UploadFiles/rewrite.docx',
            file_name: 'rewrite.docx',
            original_name: 'rewrite.docx',
            size: 128,
            upload_time: new Date().toISOString(),
          },
          tender_lx: 0,
          fund_lx: 1,
          insertion_config: {
            before_text: '第三章 招标内容及要求',
            after_text: '第四章 投标文件有关格式',
          },
          tender_data: {
            project_name: '国内公开财政货物项目',
            project_number: 'GNGK-2026-001',
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
            ifzgcg: 2,
            tender_lx: 0,
            fund_source_lx: 1,
          },
        },
      },
    }));
    mockAgentRunStream([]);

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('send-current-input-button'));

    await waitFor(() => {
      expect(mockStreamAgentRun).toHaveBeenCalledTimes(1);
    });

    expect(mockStreamAgentRun.mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({
        conversation_id: 'conv-1',
        message: '请补充技术要求',
        selected_skills: ['rewrite'],
        context_snapshot: expect.objectContaining({
          uploaded_files: [
            expect.objectContaining({
              file_path: 'D:/UploadFiles/rewrite.docx',
            }),
          ],
          rewrite_context: expect.objectContaining({
            form_type: 'gngk_hw_zc_tender',
            tender_lx: 0,
            fund_source_lx: 1,
            tender_data_snapshot: expect.objectContaining({
              ifzgcg: 2,
              fund_source_lx: 1,
            }),
          }),
        }),
      })
    );
  });

  it('keeps the latest rewrite output as the default file for the next upload rewrite', async () => {
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
              content: 'latest-rewrite.docx',
              timestamp: Date.now(),
              status: 'completed',
              taskId: 'task-rewrite-finished',
              metadata: {
                messageKind: 'task-download',
                taskKind: 'rewrite',
                outputFile: 'D:/UploadFiles/latest-rewrite.docx',
                fileName: 'latest-rewrite.docx',
              },
            },
          ],
        },
      ],
      activeTaskIds: [],
      taskMessageMap: {
        'task-rewrite-finished': {
          downloadMessageId: 'msg-download',
        },
      },
      taskSummaries: {
        'task-rewrite-finished': {
          task_id: 'task-rewrite-finished',
          task_kind: 'rewrite',
          status: 'completed',
          updated_at: Date.now(),
        },
      },
      conversationDrafts: {
        'conv-1': {

          pending_rewrite_prompt: '请继续修改',
          pending_rewrite_task_id: 'task-rewrite-finished',
          rewrite_file: {
            id: 'old-file',
            file_path: 'D:/UploadFiles/old-rewrite.docx',
            file_name: 'old-rewrite.docx',
            original_name: 'old-rewrite.docx',
            size: 256,
            upload_time: new Date().toISOString(),
          },
        },
      },
    }));

    render(<ChatPanel />);

    await waitFor(() => {
      const draft = useChatStore.getState().getConversationDraft('conv-1');
      expect(draft?.pending_rewrite_task_id).toBeUndefined();
      expect(draft?.rewrite_file?.file_path).toBe('D:/UploadFiles/latest-rewrite.docx');
      expect(draft?.rewrite_file?.original_name).toBe('latest-rewrite.docx');
    });
  });

  it('creates a comment supplement task from a generate download card', async () => {
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
              content: 'output.docx',
              timestamp: Date.now(),
              status: 'completed',
              taskId: 'task-generate-finished',
              metadata: {
                messageKind: 'task-download',
                taskKind: 'generate',
                outputFile: 'D:/UploadFiles/output.docx',
                fileName: 'output.docx',
              },
            },
          ],
        },
      ],
      activeTaskIds: [],
      taskMessageMap: {
        'task-generate-finished': {
          downloadMessageId: 'msg-download',
        },
      },
      taskSummaries: {},
      conversationDrafts: {
        'conv-1': {
          model: 'qwen',
        },
      },
    }));
    mockCreateCommentSupplementTask.mockResolvedValue({
      task_id: 'task-comment-supplement',
      task_kind: 'comment_supplement',
      status: 'queued',
      queue_position: 0,
      waiting_count: 0,
    });

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('comment-supplement-button'));

    await waitFor(() => {
      expect(mockCreateCommentSupplementTask).toHaveBeenCalledWith({
        conversation_id: 'conv-1',
        source_file: 'D:/UploadFiles/output.docx',
        model: 'qwen',
      });
      const conversation = useChatStore.getState().conversations[0];
      expect(conversation.currentTaskId).toBe('task-comment-supplement');
      expect(useChatStore.getState().taskMessageMap['task-comment-supplement']).toEqual(
        expect.objectContaining({
          logMessageId: expect.any(String),
        })
      );
      expect(useChatStore.getState().taskSummaries['task-comment-supplement']).toMatchObject({
        task_kind: 'comment_supplement',
        status: 'queued',
      });
      expect(conversation.messages).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            content: '正在创建补充批注任务',
            metadata: expect.objectContaining({
              chatKind: 'task-notice',
            }),
          }),
        ])
      );
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

    mockAgentRunStream([
      {
        event: 'done',
        data: {
          run_id: 'run-1',
          message: '重试成功内容',
        },
      },
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

    expect(mockStreamAgentRun).toHaveBeenCalledTimes(1);
  });

  it('creates rewrite task cards from agent run task_accepted events', async () => {
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
              content: 'output.docx',
              timestamp: Date.now(),
              status: 'completed',
              taskId: 'task-generate-finished',
              metadata: {
                messageKind: 'task-download',
                taskKind: 'generate',
                outputFile: 'D:/UploadFiles/output.docx',
                fileName: 'output.docx',
              },
            },
          ],
        },
      ],
      activeTaskIds: [],
      taskSummaries: {},
      conversationDrafts: {
        'conv-1': {
          chat_input: '请帮我改写这一段内容',
        },
      },
    }));

    mockAgentRunStream([
      {
        event: 'run_started',
        data: {
          run_id: 'run-1',
          conversation_id: 'conv-1',
          model: 'deepseek',
          runtime: 'fake',
          selected_skills: [],
        },
      },
      {
        event: 'thinking_stage',
        data: {
          run_id: 'run-1',
          stage: 'understand',
          label: '理解需求',
          status: 'completed',
          summary: '已识别为 rewrite 请求',
          selected_skill: 'rewrite',
        },
      },
      {
        event: 'thinking_stage',
        data: {
          run_id: 'run-1',
          stage: 'guard',
          label: '检查上下文',
          status: 'completed',
          summary: '检测到当前会话已有可改写文档。',
          selected_skill: 'rewrite',
          guard_result: 'passed',
        },
      },
      {
        event: 'tool_call',
        data: {
          run_id: 'run-1',
          tool_name: 'create_rewrite_task_tool',
          status: 'completed',
          summary: 'fake runtime 已调用 create_rewrite_task_tool。',
          task_kind: 'rewrite',
        },
      },
      {
        event: 'task_accepted',
        data: {
          run_id: 'run-1',
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
      const taskGroup = useChatStore.getState().findTaskMessageGroup('task-rewrite');
      const thinkingMessage = conversation.messages.find((message) => message.metadata?.agentThinking);
      expect(conversation.currentTaskId).toBe('task-rewrite');
      expect(draft?.pending_rewrite_task_id).toBe('task-rewrite');
      expect(conversation.messages).toHaveLength(3);
      expect(conversation.messages[1]).toMatchObject({
        type: 'user',
        metadata: {
          chatKind: 'rewrite',
        },
      });
      expect(thinkingMessage).toBeUndefined();
      expect(taskGroup?.logMessage).toMatchObject({
        taskId: 'task-rewrite',
        status: 'generating',
        metadata: {
          messageKind: 'task-log',
          taskKind: 'rewrite',
        },
      });
      expect(taskGroup?.contentMessage).toBeUndefined();
    });

    expect(mockStreamAgentRun).toHaveBeenCalledTimes(1);
    expect(mockStreamAgentRun.mock.calls[0]?.[0]).toMatchObject({
      conversation_id: 'conv-1',
      message: '请帮我改写这一段内容',
      model: 'deepseek',
      selected_skills: [],
      context_snapshot: {
        rewrite_available: true,
        uploaded_files: [],
      },
    });
    expect(mockStreamAgentRun.mock.calls[0]?.[0]).not.toHaveProperty('generation_mode');
    expect(mockStreamAgentRun.mock.calls[0]?.[0]).not.toHaveProperty('comment_generation_mode');
  });

  it('keeps fake agent run task cards visible without tracking them as active tasks', async () => {
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
              content: 'output.docx',
              timestamp: Date.now(),
              status: 'completed',
              taskId: 'task-generate-finished',
              metadata: {
                messageKind: 'task-download',
                taskKind: 'generate',
                outputFile: 'D:/UploadFiles/output.docx',
                fileName: 'output.docx',
              },
            },
          ],
        },
      ],
      activeTaskIds: [],
      taskSummaries: {},
      conversationDrafts: {
        'conv-1': {
          chat_input: '请帮我改写这一段内容',
        },
      },
    }));

    mockAgentRunStream([
      {
        event: 'run_started',
        data: {
          run_id: 'run-1',
          conversation_id: 'conv-1',
          model: 'deepseek',
          runtime: 'fake',
          selected_skills: [],
        },
      },
      {
        event: 'thinking_stage',
        data: {
          run_id: 'run-1',
          stage: 'understand',
          label: '理解需求',
          status: 'completed',
          summary: '已识别为 rewrite 请求',
          selected_skill: 'rewrite',
        },
      },
      {
        event: 'thinking_stage',
        data: {
          run_id: 'run-1',
          stage: 'guard',
          label: '检查上下文',
          status: 'completed',
          summary: '检测到当前会话已有可改写文档。',
          selected_skill: 'rewrite',
          guard_result: 'passed',
        },
      },
      {
        event: 'task_accepted',
        data: {
          run_id: 'run-1',
          task_id: 'fake-rewrite-task-1',
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
      const state = useChatStore.getState();
      const conversation = state.conversations[0];
      const taskGroup = state.findTaskMessageGroup('fake-rewrite-task-1');
      const thinkingMessage = conversation.messages.find((message) => message.metadata?.agentThinking);
      expect(conversation.currentTaskId).toBeUndefined();
      expect(state.activeTaskIds).toEqual([]);
      expect(state.getTaskSummary('fake-rewrite-task-1')).toBeNull();
      expect(thinkingMessage).toBeUndefined();
      expect(taskGroup?.logMessage).toMatchObject({
        taskId: 'fake-rewrite-task-1',
        status: 'generating',
      });
      expect(taskGroup?.contentMessage).toBeUndefined();
      expect(state.getConversationDraft('conv-1')?.pending_rewrite_task_id).toBeUndefined();
    });

    act(() => {
      useChatStore.getState().updateConversationDraft('conv-1', {
        chat_input: '你好',
      });
    });

    mockAgentRunStream([
      {
        event: 'needs_input',
        data: {
          run_id: 'run-2',
          message: '请说明这次要执行 rewrite。',
          missing_requirements: ['selected_skill'],
        },
      },
    ]);

    fireEvent.click(screen.getByTestId('send-current-input-button'));

    await waitFor(() => {
      const conversation = useChatStore.getState().conversations[0];
      expect(conversation.messages[conversation.messages.length - 1]).toMatchObject({
        type: 'ai',
        content: '请说明这次要执行 rewrite。',
        status: 'completed',
      });
    });

    expect(mockStreamAgentRun).toHaveBeenCalledTimes(2);
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

    mockAgentRunStream([
      {
        event: 'done',
        data: {
          run_id: 'run-1',
          message: '你好，请问有什么可以帮你？',
        },
      },
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

  it('clears the normal chat draft immediately after send is accepted', async () => {
    const deferred = createDeferred<void>();

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

    mockStreamAgentRun.mockImplementationOnce(async (_payload, options = {}) => {
      await deferred.promise;
      await options.onEvent?.({
        event: 'done',
        data: {
          run_id: 'run-1',
          message: '你好，请问有什么可以帮你？',
        },
      });
    });

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('send-current-input-button'));

    await waitFor(() => expect(mockStreamAgentRun).toHaveBeenCalledTimes(1));
    expect(useChatStore.getState().getConversationDraft('conv-1')?.chat_input).toBe('');

    deferred.resolve();

    await waitFor(() => {
      const conversation = useChatStore.getState().conversations[0];
      expect(conversation.messages[1].status).toBe('completed');
    });
  });

  it('keeps the composer loading while agent run is active and errors incomplete streams', async () => {
    const deferred = createDeferred<void>();

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
          chat_input: '请帮我修改第三章',
        },
      },
    }));

    mockStreamAgentRun.mockImplementationOnce(async (_payload, options = {}) => {
      await options.onEvent?.({
        event: 'run_started',
        data: {
          run_id: 'run-incomplete',
          conversation_id: 'conv-1',
          model: 'deepseek',
          runtime: 'fake',
          selected_skills: [],
        },
      });
      await deferred.promise;
    });

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('send-current-input-button'));

    await waitFor(() => {
      expect(screen.getByTestId('chat-input')).toHaveAttribute('data-loading', 'true');
      const conversation = useChatStore.getState().conversations[0];
      const thinkingMessage = conversation.messages.find((message) => message.metadata?.agentThinking);
      expect(thinkingMessage).toMatchObject({
        status: 'generating',
        metadata: {
          agentThinking: {
            runId: 'run-incomplete',
          },
        },
      });
    });

    deferred.resolve();

    await waitFor(() => {
      expect(screen.getByTestId('chat-input')).toHaveAttribute('data-loading', 'false');
      const conversation = useChatStore.getState().conversations[0];
      const thinkingMessage = conversation.messages.find((message) => message.metadata?.agentThinking);
      expect(thinkingMessage).toMatchObject({
        status: 'error',
        error: '任务助手流未返回完成事件，请重试',
        metadata: {
          agentThinking: {
            terminalState: 'error',
          },
        },
      });
    });
  });

  it('clears the rewrite draft immediately after agent run starts and restores pending task tracking on acceptance', async () => {
    const deferred = createDeferred<void>();

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

          rewrite_file: {
            id: 'file-1',
            file_path: 'D:/UploadFiles/rewrite.docx',
            file_name: 'rewrite.docx',
            original_name: 'rewrite.docx',
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

    mockStreamAgentRun.mockImplementationOnce(async (_payload, options = {}) => {
      await deferred.promise;
      await options.onEvent?.({
        event: 'task_accepted',
        data: {
          run_id: 'run-rewrite-deferred',
          task_id: 'task-rewrite',
          task_kind: 'rewrite',
          status: 'queued',
          queue_position: 0,
          waiting_count: 0,
        },
      });
    });

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('send-current-input-button'));

    await waitFor(() => expect(mockStreamAgentRun).toHaveBeenCalledTimes(1));
    expect(useChatStore.getState().getConversationDraft('conv-1')?.chat_input).toBe('');

    deferred.resolve();

    await waitFor(() => {
      const draft = useChatStore.getState().getConversationDraft('conv-1');
      expect(draft?.pending_rewrite_task_id).toBe('task-rewrite');
    });
  });

  it('shows needs_input follow-up messages without creating a task card', async () => {
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

    mockAgentRunStream([
      {
        event: 'run_started',
        data: {
          run_id: 'run-1',
          conversation_id: 'conv-1',
          model: 'deepseek',
          runtime: 'fake',
          selected_skills: [],
        },
      },
      {
        event: 'thinking_stage',
        data: {
          run_id: 'run-1',
          stage: 'guard',
          label: '检查上下文',
          status: 'completed',
          summary: 'fake runtime 暂时只支持 rewrite 任务创建。',
          guard_result: 'needs_input',
        },
      },
      {
        event: 'needs_input',
        data: {
          run_id: 'run-1',
          message: '请说明这次要执行 rewrite。',
          missing_requirements: ['selected_skill'],
        },
      },
    ]);

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('send-current-input-button'));

    await waitFor(() => {
      const conversation = useChatStore.getState().conversations[0];
      expect(conversation.currentTaskId).toBeUndefined();
      expect(conversation.messages).toHaveLength(3);
      expect(conversation.messages.find((message) => message.metadata?.agentThinking)).toMatchObject({
        status: 'completed',
        metadata: {
          agentThinking: expect.objectContaining({
            terminalState: 'needs_input',
          }),
        },
      });
      expect(conversation.messages[1]).toMatchObject({
        type: 'ai',
        status: 'completed',
        metadata: {
          agentThinking: expect.objectContaining({
            terminalState: 'needs_input',
          }),
        },
      });
      expect(conversation.messages[2]).toMatchObject({
        type: 'ai',
        content: '请说明这次要执行 rewrite。',
        status: 'completed',
      });
    });
  });

  it('shows explicit error messages when the agent run returns an error terminal', async () => {
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
          chat_input: '请帮我改写这一段内容',
        },
      },
    }));

    mockAgentRunStream([
      {
        event: 'run_started',
        data: {
          run_id: 'run-1',
          conversation_id: 'conv-1',
          model: 'deepseek',
          runtime: 'fake',
          selected_skills: [],
        },
      },
      {
        event: 'error',
        data: {
          run_id: 'run-1',
          code: 'AGENT_RUN_FAILED',
          message: 'agent run 执行失败，请稍后重试',
        },
      },
    ]);

    render(<ChatPanel />);

    fireEvent.click(screen.getByTestId('send-current-input-button'));

    await waitFor(() => {
      const conversation = useChatStore.getState().conversations[0];
      expect(conversation.currentTaskId).toBeUndefined();
      expect(conversation.messages).toHaveLength(3);
      expect(conversation.messages[1]).toMatchObject({
        type: 'ai',
        status: 'error',
        metadata: {
          agentThinking: expect.objectContaining({
            terminalState: 'error',
          }),
        },
      });
      expect(conversation.messages[2]).toMatchObject({
        type: 'ai',
        content: 'agent run 执行失败，请稍后重试',
        status: 'error',
      });
      expect(screen.getByTestId('chat-input')).toHaveAttribute('data-loading', 'false');
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

    mockStreamAgentRun.mockImplementationOnce(
      async (_payload, options = {}) =>
        new Promise<void>((_resolve, reject) => {
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
      expect(screen.getByTestId('chat-input')).toHaveAttribute('data-loading', 'true');
    });

    fireEvent.click(screen.getByTestId('cancel-chat-button'));

    await waitFor(() => {
      const conversation = useChatStore.getState().conversations[0];
      expect(screen.getByTestId('chat-input')).toHaveAttribute('data-loading', 'false');
      expect(conversation.messages).toHaveLength(1);
      expect(conversation.messages[0]).toMatchObject({
        type: 'user',
        content: '帮我写一段说明',
      });
    });
  });
});
