import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MessageList } from '@/components/chat/MessageList';
import type { Message } from '@/types/chat';

function createTaskMessages(): Message[] {
  return [
    {
      id: 'msg-log',
      conversationId: 'conv-1',
      type: 'ai',
      content: '',
      timestamp: 1,
      status: 'completed',
      taskId: 'task-1',
      metadata: {
        messageKind: 'task-log',
        logs: [
          {
            id: 'log-1',
            timestamp: Date.now(),
            level: 'info',
            message: '开始处理',
          },
        ],
      },
    },
    {
      id: 'msg-content',
      conversationId: 'conv-1',
      type: 'ai',
      content: '这是生成内容',
      timestamp: 2,
      status: 'completed',
      taskId: 'task-1',
      metadata: {
        messageKind: 'task-content',
      },
    },
    {
      id: 'msg-download',
      conversationId: 'conv-1',
      type: 'ai',
      content: 'output.docx',
      timestamp: 3,
      status: 'completed',
      taskId: 'task-1',
      metadata: {
        messageKind: 'task-download',
        outputFile: 'D:/UploadFiles/output.docx',
        fileName: 'output.docx',
        styleWriteback: {
          summary: '样式回填: 抽取=2, 尝试=2, 成功=1, 跳过=1, 失败=0',
          extracted: 2,
          attempted: 2,
          applied: 1,
          skipped: 1,
          failed: 0,
          applied_by_style: { bold: 1 },
          skipped_by_reason: { low_confidence: 1 },
        },
      },
    },
  ];
}

function createGeneratingTaskMessages(): Message[] {
  return createTaskMessages().map((message) =>
    message.metadata?.messageKind === 'task-log'
      ? {
          ...message,
          status: 'generating' as const,
        }
      : message
  );
}

function createStyleWritebackTaskMessages(): Message[] {
  const messages = createTaskMessages();
  messages[0] = {
    ...messages[0],
    metadata: {
      ...(messages[0].metadata || {}),
      messageKind: 'task-log',
      logs: [
        {
          id: 'style-log-success',
          timestamp: Date.now(),
          level: 'info',
          message: '步骤6：样式回填成功[2/7] 加粗 | "二、技术需求" -> "二、技术需求"',
        },
        {
          id: 'style-log-skip',
          timestamp: Date.now() + 1,
          level: 'warn',
          message: '步骤6：样式回填跳过[5/7] 字体颜色 | "提供" | 原因：相似度不足',
        },
        {
          id: 'style-log-failure',
          timestamp: Date.now() + 2,
          level: 'error',
          message: '步骤6：样式回填失败[6/7] 删除线、字体颜色 | "标注“★”的项目" | 错误：RPC write failed',
        },
      ],
    },
  };
  return messages;
}

function createUserMessage(content = '你好'): Message[] {
  return [
    {
      id: 'msg-user',
      conversationId: 'conv-1',
      type: 'user',
      content,
      timestamp: 1,
      status: 'sent',
    },
  ];
}

function createAiMessage(content = '你好'): Message[] {
  return [
    {
      id: 'msg-ai',
      conversationId: 'conv-1',
      type: 'ai',
      content,
      timestamp: 1,
      status: 'completed',
    },
  ];
}

describe('MessageList', () => {
  beforeEach(() => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: jest.fn().mockResolvedValue(undefined),
      },
    });
  });

  it('renders task messages in log -> content -> download order', () => {
    render(<MessageList messages={createTaskMessages()} />);

    const logCard = screen.getByText('进度日志');
    const contentCard = screen.getByText('AI 生成内容');
    const downloadCard = screen.getByText('文档已生成');

    expect(logCard.compareDocumentPosition(contentCard) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(contentCard.compareDocumentPosition(downloadCard) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('renders log text in a wrapping style to avoid horizontal overflow', () => {
    render(<MessageList messages={createTaskMessages()} />);

    expect(screen.getByText('开始处理')).toHaveClass('break-all', 'whitespace-pre-wrap');
  });

  it('collapses generating task logs to a summary until the user expands them', () => {
    render(<MessageList messages={createGeneratingTaskMessages()} />);

    expect(screen.getByText('最新')).toBeInTheDocument();
    expect(screen.getByText('开始处理')).toHaveClass('truncate', 'break-all');

    fireEvent.click(screen.getByRole('button', { name: '展开进度日志' }));

    expect(screen.getByText('开始处理')).toHaveClass('break-all', 'whitespace-pre-wrap');
    expect(screen.getByRole('button', { name: '收起进度日志' })).toBeInTheDocument();
  });

  it('renders only recent task logs while keeping the full log count available', () => {
    const messages = createTaskMessages();
    messages[0] = {
      ...messages[0],
      metadata: {
        ...(messages[0].metadata || {}),
        messageKind: 'task-log',
        logs: Array.from({ length: 130 }, (_, index) => ({
          id: `log-${index}`,
          timestamp: Date.now() + index,
          level: 'info',
          message: `日志 ${index}`,
        })),
      },
    };

    render(<MessageList messages={messages} />);

    expect(screen.getByText('最近 80 / 共 130 条')).toBeInTheDocument();
    expect(screen.queryByText('日志 49')).not.toBeInTheDocument();
    expect(screen.getByText('日志 50')).toBeInTheDocument();
    expect(screen.getByText('日志 129')).toBeInTheDocument();
  });

  it('renders style writeback logs with clear status badges and concise details', () => {
    render(<MessageList messages={createStyleWritebackTaskMessages()} />);

    expect(screen.getByText('回填成功')).toHaveClass('text-green-700', 'bg-green-50');
    expect(screen.getByText('回填跳过')).toHaveClass('text-amber-700', 'bg-amber-50');
    expect(screen.getByText('回填失败')).toHaveClass('text-red-700', 'bg-red-50');

    expect(
      screen.getByText('步骤6 [2/7] 加粗 | "二、技术需求" -> "二、技术需求"')
    ).toHaveClass('text-green-800');
    expect(
      screen.getByText('步骤6 [5/7] 字体颜色 | "提供" | 原因：相似度不足')
    ).toHaveClass('text-amber-800');
    expect(
      screen.getByText('步骤6 [6/7] 删除线、字体颜色 | "标注“★”的项目" | 错误：RPC write failed')
    ).toHaveClass('text-red-800');
  });

  it('copies condensed style writeback logs using the user-facing text', async () => {
    render(<MessageList messages={createStyleWritebackTaskMessages()} />);

    fireEvent.click(screen.getByRole('button', { name: '复制进度日志' }));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalled();
    });

    const clipboardCalls = (navigator.clipboard.writeText as jest.Mock).mock.calls;
    const copiedText = clipboardCalls[clipboardCalls.length - 1]?.[0];
    expect(copiedText).toContain('步骤6：样式回填成功[2/7] 加粗 | "二、技术需求" -> "二、技术需求"');
    expect(copiedText).toContain('步骤6：样式回填跳过[5/7] 字体颜色 | "提供" | 原因：相似度不足');
    expect(copiedText).not.toContain('候选=');
    expect(copiedText).not.toContain('得分=');
  });

  it('triggers existing download handler from task download card', () => {
    const onDownload = jest.fn();
    render(<MessageList messages={createTaskMessages()} onDownload={onDownload} />);

    fireEvent.click(screen.getByRole('button', { name: '下载文件' }));

    expect(onDownload).toHaveBeenCalledWith('D:/UploadFiles/output.docx', 'output.docx');
  });

  it('does not render style writeback summary on the download card when present', () => {
    render(<MessageList messages={createTaskMessages()} />);

    expect(
      screen.queryByText('样式回填: 抽取=2, 尝试=2, 成功=1, 跳过=1, 失败=0')
    ).not.toBeInTheDocument();
  });

  it('does not show retry action on failed task content card', () => {
    const onRetry = jest.fn();
    const messages = createTaskMessages();
    messages[1] = {
      ...messages[1],
      status: 'error',
      error: '生成失败',
      metadata: {
        ...(messages[1].metadata || {}),
        messageKind: 'task-content',
      },
    };

    render(<MessageList messages={messages} onRetry={onRetry} />);

    expect(screen.queryByRole('button', { name: '重试' })).not.toBeInTheDocument();
    expect(onRetry).not.toHaveBeenCalled();
  });

  it('renders user messages in a content-sized bubble capped above half of the chat width', () => {
    render(<MessageList messages={createUserMessage()} />);

    expect(screen.getByTestId('user-message-frame')).toHaveClass('w-fit', 'max-w-[65%]');
    expect(screen.getByTestId('user-message-bubble')).toHaveClass(
      'w-fit',
      'max-w-full',
      'bg-blue-500',
      'rounded-tr-sm'
    );
    expect(screen.getByTestId('user-message-actions')).toHaveClass('opacity-0', 'pointer-events-none');
    expect(screen.getByTestId('user-message-time')).toHaveClass('opacity-100');
  });

  it('copies the user message from the inline copy button', async () => {
    render(<MessageList messages={createUserMessage('请复制这段内容')} />);

    fireEvent.mouseEnter(screen.getByTestId('user-message-frame'));
    fireEvent.click(screen.getByRole('button', { name: '复制用户消息' }));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('请复制这段内容');
    });
  });

  it('shows the inline action row only when hovering the user bubble area', () => {
    render(<MessageList messages={createUserMessage('悬浮显示操作')} />);

    const frame = screen.getByTestId('user-message-frame');
    const actions = screen.getByTestId('user-message-actions');
    const time = screen.getByTestId('user-message-time');
    const copyButton = screen.getByRole('button', { name: '复制用户消息' });

    expect(actions).toHaveClass('opacity-0', 'pointer-events-none');
    expect(time).toHaveClass('opacity-100');
    expect(copyButton).toHaveAttribute('tabindex', '-1');

    fireEvent.mouseEnter(frame);

    expect(actions).toHaveClass('opacity-100');
    expect(time).toHaveClass('opacity-0');
    expect(copyButton).toHaveAttribute('tabindex', '0');

    fireEvent.mouseLeave(frame);

    expect(actions).toHaveClass('opacity-0', 'pointer-events-none');
    expect(time).toHaveClass('opacity-100');
    expect(copyButton).toHaveAttribute('tabindex', '-1');
  });

  it('preserves user-authored line breaks in message bubbles', () => {
    render(<MessageList messages={createUserMessage('第一行\n第二行')} />);

    expect(screen.getByTestId('user-message-text')).toHaveClass('whitespace-pre-wrap', 'break-words');
    expect(screen.getByTestId('user-message-text').textContent).toBe('第一行\n第二行');
  });

  it('renders the user message before the avatar', () => {
    render(<MessageList messages={createUserMessage()} />);

    const frame = screen.getByTestId('user-message-frame');
    const avatar = screen.getByTestId('user-message-avatar');

    expect(frame.nextElementSibling).toBe(avatar);
  });

  it('renders inline markdown safely when the split regex produces optional groups', () => {
    render(
      <MessageList
        messages={createAiMessage('请看 **重点** 和 [文档](https://example.com/doc) 的说明')}
      />
    );

    expect(screen.getByText('重点')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '文档' })).toHaveAttribute(
      'href',
      'https://example.com/doc'
    );
  });
});
