import { fireEvent, render, screen } from '@testing-library/react';
import { ChatInput } from '@/components/chat/ChatInput';
import { useState } from 'react';
import type { ConversationDraftFile } from '@/stores/chatStore';

function ControlledChatInput({
  onSend = jest.fn(),
  selectedModel = 'deepseek',
  onModelChange = jest.fn(),
  loading = false,
  actionMode = 'send',
  disabled = false,
  noticeMessage = null,
}: {
  onSend?: (message: string) => void;
  selectedModel?: 'deepseek' | 'qwen' | 'doubao';
  onModelChange?: (model: 'deepseek' | 'qwen' | 'doubao') => void;
  loading?: boolean;
  actionMode?: 'send' | 'cancel';
  disabled?: boolean;
  noticeMessage?: string | null;
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
      noticeMessage={noticeMessage}
    />
  );
}

function ControlledEditChatInput({
  onEditFileSelect = jest.fn(),
  initialEditFile = null,
}: {
  onEditFileSelect?: (file: File) => void | Promise<void>;
  initialEditFile?: ConversationDraftFile | null;
}) {
  const [value, setValue] = useState('');
  const [editFile, setEditFile] = useState<ConversationDraftFile | null>(initialEditFile);

  return (
    <ChatInput
      value={value}
      onValueChange={setValue}
      onSend={jest.fn()}
      selectedModel="deepseek"
      onModelChange={jest.fn()}
      inputMode={editFile ? 'edit' : 'normal'}
      editFile={editFile}
      onEditFileSelect={async (file) => {
        await onEditFileSelect(file);
        setEditFile({
          id: 'edit-file-1',
          file_path: '/tmp/test.docx',
          file_name: 'test.docx',
          original_name: file.name,
          size: file.size,
          upload_time: new Date().toISOString(),
        });
      }}
      onEditFileRemove={() => setEditFile(null)}
    />
  );
}

function ProgrammaticValueChatInput() {
  const [value, setValue] = useState('');

  return (
    <>
      <button type="button" onClick={() => setValue('第一行\n第二行\n第三行')}>
        set value
      </button>
      <ChatInput
        value={value}
        onValueChange={setValue}
        onSend={jest.fn()}
        selectedModel="deepseek"
        onModelChange={jest.fn()}
      />
    </>
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

    const textarea = screen.getByRole('textbox');

    fireEvent.change(textarea, { target: { value: '  测试消息  ' } });
    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' });

    expect(handleSend).toHaveBeenCalledWith('测试消息');
    expect(textarea).toHaveValue('');
    expect(textarea).toHaveStyle({ height: '44px', overflowY: 'hidden' });
  });

  it('auto-resizes the textarea and clamps it at the configured max height', () => {
    render(<ControlledChatInput />);

    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;

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

  it('resizes the textarea when the draft is updated programmatically', () => {
    render(<ProgrammaticValueChatInput />);

    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;
    Object.defineProperty(textarea, 'scrollHeight', {
      configurable: true,
      value: 96,
    });

    fireEvent.click(screen.getByRole('button', { name: 'set value' }));

    expect(textarea).toHaveValue('第一行\n第二行\n第三行');
    expect(textarea).toHaveStyle({ height: '96px', overflowY: 'hidden' });
  });

  it('allows editing while loading in cancel mode without clearing draft on Enter', () => {
    const handleSend = jest.fn();

    render(<ControlledChatInput onSend={handleSend} loading actionMode="cancel" />);

    const textarea = screen.getByRole('textbox');
    expect(textarea).not.toBeDisabled();

    fireEvent.change(textarea, { target: { value: '这条消息先写好，等生成结束再发' } });
    expect(textarea).toHaveValue('这条消息先写好，等生成结束再发');

    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' });
    expect(handleSend).not.toHaveBeenCalled();
    expect(textarea).toHaveValue('这条消息先写好，等生成结束再发');
  });

  it('opens and closes the explicit plus menu', () => {
    render(<ControlledChatInput />);

    fireEvent.click(screen.getByTestId('chat-plus-trigger'));
    expect(screen.getByTestId('chat-plus-menu')).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByTestId('chat-plus-menu')).not.toBeInTheDocument();
  });

  it('rejects non-word files in edit mode entry', () => {
    render(<ControlledChatInput />);

    fireEvent.change(screen.getByTestId('chat-edit-file-input'), {
      target: {
        files: [new File(['x'], 'invalid.pdf', { type: 'application/pdf' })],
      },
    });

    expect(screen.getByTestId('chat-input-notice')).toHaveTextContent('仅支持上传 .doc 或 .docx 文件');
  });

  it('shows, removes, and replaces the selected edit file card', async () => {
    const handleEditFileSelect = jest.fn();
    render(<ControlledEditChatInput onEditFileSelect={handleEditFileSelect} />);

    fireEvent.change(screen.getByTestId('chat-edit-file-input'), {
      target: {
        files: [
          new File(['hello'], 'first.docx', {
            type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          }),
        ],
      },
    });

    expect(handleEditFileSelect).toHaveBeenCalledTimes(1);
    expect(await screen.findByTestId('chat-edit-file-card')).toHaveTextContent('first.docx');

    fireEvent.click(screen.getByTestId('chat-edit-file-remove'));
    expect(screen.queryByTestId('chat-edit-file-card')).not.toBeInTheDocument();

    fireEvent.change(screen.getByTestId('chat-edit-file-input'), {
      target: {
        files: [new File(['world'], 'second.doc', { type: 'application/msword' })],
      },
    });

    expect(handleEditFileSelect).toHaveBeenCalledTimes(2);
    expect(await screen.findByTestId('chat-edit-file-card')).toHaveTextContent('second.doc');
  });
});
