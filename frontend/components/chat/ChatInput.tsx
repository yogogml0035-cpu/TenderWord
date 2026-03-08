'use client';

import React, { useState, useRef, useCallback } from 'react';
import { Loader2, Send } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ModelType } from '@/components/forms/ModelSelector';
import { ChatModelPicker } from './ChatModelPicker';

const MIN_TEXTAREA_HEIGHT = 44;
const MAX_TEXTAREA_HEIGHT = 180;

interface ChatInputProps {
  onSend: (message: string) => void;
  selectedModel: ModelType;
  onModelChange: (model: ModelType) => void;
  disabled?: boolean;
  placeholder?: string;
  loading?: boolean;
}

export function ChatInput({
  onSend,
  selectedModel,
  onModelChange,
  disabled = false,
  placeholder = '输入消息...',
  loading = false,
}: ChatInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const inputLocked = disabled || loading;
  const resetTextareaHeight = useCallback((textarea: HTMLTextAreaElement | null) => {
    if (!textarea) {
      return;
    }

    textarea.style.height = `${MIN_TEXTAREA_HEIGHT}px`;
    textarea.style.overflowY = 'hidden';
    textarea.scrollTop = 0;
  }, []);

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || inputLocked) return;

    onSend(trimmed);
    setInput('');
    resetTextareaHeight(textareaRef.current);
  }, [input, inputLocked, onSend, resetTextareaHeight]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const target = e.target;
    setInput(target.value);

    target.style.height = '0px';

    const nextHeight = Math.min(
      Math.max(target.scrollHeight, MIN_TEXTAREA_HEIGHT),
      MAX_TEXTAREA_HEIGHT
    );

    target.style.height = `${nextHeight}px`;
    target.style.overflowY = target.scrollHeight > MAX_TEXTAREA_HEIGHT ? 'auto' : 'hidden';
  };

  const isEmpty = !input.trim();

  return (
    <div className="border-t border-slate-200 bg-gradient-to-b from-white via-slate-50/60 to-white px-4 py-2.5">
      <div
        className={cn(
          'rounded-[26px] border border-slate-200 bg-white px-3 py-2.5 shadow-lg shadow-slate-200/70 transition-all duration-200',
          inputLocked && 'opacity-90'
        )}
      >
        <div className="pb-1.5">
          <ChatModelPicker
            value={selectedModel}
            onChange={onModelChange}
            disabled={inputLocked}
          />
        </div>

        <div className="relative">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={inputLocked}
            rows={1}
            className={cn(
              'block w-full resize-none bg-transparent px-2 py-2.5 pr-14 text-[15px] leading-6 text-slate-800 transition-colors duration-200 placeholder:text-slate-400 focus:outline-none',
              inputLocked && 'cursor-not-allowed text-slate-500'
            )}
            style={{
              boxSizing: 'border-box',
              minHeight: `${MIN_TEXTAREA_HEIGHT}px`,
              height: `${MIN_TEXTAREA_HEIGHT}px`,
              maxHeight: `${MAX_TEXTAREA_HEIGHT}px`,
              overflowY: 'hidden',
            }}
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={isEmpty || inputLocked}
            aria-label={loading ? '发送中' : '发送消息'}
            className={cn(
              'absolute right-1.5 bottom-1.5 flex h-10 w-10 items-center justify-center rounded-2xl transition-all duration-200',
              isEmpty || inputLocked
                ? 'cursor-not-allowed bg-slate-200 text-slate-400'
                : 'bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-200 hover:-translate-y-0.5 hover:from-blue-600 hover:to-blue-700'
            )}
          >
            {loading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ChatInput;
