'use client';

import React, { useState, useRef, useCallback } from 'react';
import { Send, Loader2 } from 'lucide-react';

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
  loading?: boolean;
}

export function ChatInput({
  onSend,
  disabled = false,
  placeholder = '输入消息...',
  loading = false,
}: ChatInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || disabled || loading) return;

    onSend(trimmed);
    setInput('');

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [input, onSend, disabled, loading]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const target = e.target;
    setInput(target.value);

    // Auto-resize
    target.style.height = 'auto';
    target.style.height = Math.min(target.scrollHeight, 120) + 'px';
  };

  const isEmpty = !input.trim();

  return (
    <div className="flex items-end gap-2 border-t border-gray-200 bg-white p-3">
      <div className="relative flex-1">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled || loading}
          rows={1}
          className={`w-full resize-none rounded border px-4 py-2 pr-10 transition-colors duration-200 focus:border-transparent focus:ring-2 focus:ring-blue-500 focus:outline-none ${disabled || loading ? 'cursor-not-allowed bg-gray-100' : 'bg-white'} ${isEmpty ? 'border-gray-300' : 'border-blue-300'} `}
        />
        <div className="absolute right-3 bottom-2.5 text-xs text-gray-400">
          {input.length > 0 && `${input.length} 字符`}
        </div>
      </div>

      <button
        onClick={handleSend}
        disabled={isEmpty || disabled || loading}
        className={`flex h-11 w-11 items-center justify-center rounded transition-colors duration-200 ${
          isEmpty || disabled || loading
            ? 'cursor-not-allowed bg-gray-200 text-gray-400'
            : 'bg-blue-500 text-white shadow-sm hover:bg-blue-600 hover:shadow-md'
        } `}
      >
        {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
      </button>
    </div>
  );
}

export default ChatInput;
