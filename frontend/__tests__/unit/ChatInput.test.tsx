import { fireEvent, render, screen } from '@testing-library/react';
import { ChatInput } from '@/components/chat/ChatInput';
import { useState } from 'react';

function ControlledChatInput({
  onSend = jest.fn(),
  selectedModel = 'deepseek',
  onModelChange = jest.fn(),
  loading = false,
  actionMode = 'send',
  disabled = false,
}: {
  onSend?: (message: string) => void;
  selectedModel?: 'deepseek' | 'qwen' | 'doubao';
  onModelChange?: (model: 'deepseek' | 'qwen' | 'doubao') => void;
  loading?: boolean;
  actionMode?: 'send' | 'cancel';
  disabled?: boolean;
}) {
  const [value, setValue] = useState('');

  return (
    <ChatInput
      value={value}
      onValueChange={setValue}
      onSend={onSend}
      selectedModel={selectedModel}
      onModelChange={onModelChange}
      loading={loading}
      actionMode={actionMode}
      disabled={disabled}
    />
  );
}

describe('ChatInput', () => {
  it('renders the selected model inside the composer', () => {
    render(<ControlledChatInput />);

    expect(screen.getByTestId('chat-model-trigger')).toHaveTextContent('DeepSeek');
    expect(screen.getByTestId('chat-model-trigger-content')).toHaveClass('items-center');
    expect(screen.getByTestId('chat-model-trigger')).not.toHaveTextContent('问问');
    expect(screen.queryByText('深度推理与长文本生成')).not.toBeInTheDocument();
    expect(screen.queryByText('Enter 发送，Shift + Enter 换行')).not.toBeInTheDocument();
  });

  it('opens the model picker and changes the selected model', () => {
    const handleModelChange = jest.fn();

    render(<ControlledChatInput onModelChange={handleModelChange} />);

    fireEvent.click(screen.getByTestId('chat-model-trigger'));

    expect(screen.getByRole('dialog', { name: '选择聊天模型' })).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('chat-model-option-qwen'));

    expect(handleModelChange).toHaveBeenCalledWith('qwen');
    expect(screen.queryByRole('dialog', { name: '选择聊天模型' })).not.toBeInTheDocument();
  });

  it('sends a trimmed message when Enter is pressed', () => {
    const handleSend = jest.fn();

    render(<ControlledChatInput onSend={handleSend} />);

    const textarea = screen.getByPlaceholderText('输入消息...');

    fireEvent.change(textarea, { target: { value: '  测试消息  ' } });
    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' });

    expect(handleSend).toHaveBeenCalledWith('测试消息');
    expect(textarea).toHaveValue('');
    expect(textarea).toHaveStyle({ height: '44px', overflowY: 'hidden' });
  });

  it('auto-resizes the textarea and clamps it at the configured max height', () => {
    render(<ControlledChatInput />);

    const textarea = screen.getByPlaceholderText('输入消息...') as HTMLTextAreaElement;

    Object.defineProperty(textarea, 'scrollHeight', {
      configurable: true,
      value: 72,
    });

    fireEvent.change(textarea, { target: { value: '第一行\n第二行' } });

    expect(textarea).toHaveStyle({ height: '72px', overflowY: 'hidden' });

    Object.defineProperty(textarea, 'scrollHeight', {
      configurable: true,
      value: 260,
    });

    fireEvent.change(textarea, {
      target: { value: '一段足够长的文本\n'.repeat(12) },
    });

    expect(textarea).toHaveStyle({ height: '180px', overflowY: 'auto' });
  });

  it('allows editing while loading in cancel mode without clearing draft on Enter', () => {
    const handleSend = jest.fn();

    render(<ControlledChatInput onSend={handleSend} loading actionMode="cancel" />);

    const textarea = screen.getByPlaceholderText('输入消息...');
    expect(textarea).not.toBeDisabled();

    fireEvent.change(textarea, { target: { value: '这条消息先写好，等生成结束再发' } });
    expect(textarea).toHaveValue('这条消息先写好，等生成结束再发');

    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' });
    expect(handleSend).not.toHaveBeenCalled();
    expect(textarea).toHaveValue('这条消息先写好，等生成结束再发');
  });
});
