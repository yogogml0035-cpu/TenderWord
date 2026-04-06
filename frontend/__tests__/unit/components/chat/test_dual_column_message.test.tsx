import { fireEvent, render, screen } from '@testing-library/react';
import { createEmptyDualColumnContent } from '@/lib/chat-utils';
import { DualColumnMessage } from '@/components/chat/DualColumnMessage';
import type { Message } from '@/types/chat';

function createCompletedMessage(): Message {
  return {
    id: 'msg-1',
    conversationId: 'conv-1',
    type: 'ai',
    content: {
      ...createEmptyDualColumnContent(),
      logs: [
        {
          id: 'log-1',
          timestamp: new Date('2026-03-06T13:30:23+08:00').getTime(),
          level: 'info',
          message: '[replace_content] 替换最新项目信息 完成 (6/7)',
        },
      ],
      aiContent: {
        text: '生成完成',
        timestamp: 1,
        isComplete: true,
      },
    },
    timestamp: 1,
    status: 'completed',
    metadata: {
      outputFile: 'D:/UploadFiles/output.docx',
      fileName: 'output.docx',
    },
  };
}

describe('DualColumnMessage', () => {
  beforeEach(() => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: jest.fn().mockResolvedValue(undefined),
      },
    });
  });

  it('renders the completed download button inside the left header group and keeps download working', () => {
    const onDownload = jest.fn();
    const { container } = render(
      <DualColumnMessage message={createCompletedMessage()} onDownload={onDownload} />
    );

    const button = screen.getByRole('button', { name: /下载文件/i });
    const statusText = screen.getByText('已完成');
    const header = container.querySelector('.justify-between');

    expect(header?.firstElementChild).toContainElement(button);
    expect(header?.firstElementChild).toContainElement(statusText);

    fireEvent.click(button);

    expect(onDownload).toHaveBeenCalledWith('D:/UploadFiles/output.docx', 'output.docx');
  });

  it('copies progress logs and ai content from the column header actions', async () => {
    const message = createCompletedMessage();
    render(<DualColumnMessage message={message} />);

    fireEvent.click(screen.getByRole('button', { name: '复制进度日志' }));
    expect(navigator.clipboard.writeText).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining('[replace_content] 替换最新项目信息 完成 (6/7)')
    );

    fireEvent.click(screen.getByRole('button', { name: '复制AI内容' }));
    expect(navigator.clipboard.writeText).toHaveBeenNthCalledWith(2, '生成完成');
  });

  it('keeps long log and ai text wrapped without widening message layout', () => {
    const message = createCompletedMessage();
    const longText = 'A'.repeat(800);
    message.content = {
      ...createEmptyDualColumnContent(),
      logs: [
        {
          id: 'log-long',
          timestamp: Date.now(),
          level: 'info',
          message: longText,
        },
      ],
      aiContent: {
        text: longText,
        timestamp: Date.now(),
        isComplete: true,
      },
    };

    const { container } = render(<DualColumnMessage message={message} />);

    const [logText] = screen.getAllByText(longText);
    const aiPre = container.querySelector('pre');

    expect(logText).toHaveClass('break-all', 'whitespace-pre-wrap');
    expect(aiPre).toHaveClass('break-all', 'whitespace-pre-wrap');
  });
});
