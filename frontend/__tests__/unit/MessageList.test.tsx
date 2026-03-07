import { fireEvent, render, screen } from '@testing-library/react';
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
      },
    },
  ];
}

describe('MessageList', () => {
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

  it('triggers existing download handler from task download card', () => {
    const onDownload = jest.fn();
    render(<MessageList messages={createTaskMessages()} onDownload={onDownload} />);

    fireEvent.click(screen.getByRole('button', { name: '下载文件' }));

    expect(onDownload).toHaveBeenCalledWith('D:/UploadFiles/output.docx', 'output.docx');
  });

  it('shows retry action on failed task content card and invokes callback', () => {
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

    fireEvent.click(screen.getByRole('button', { name: '重试' }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
