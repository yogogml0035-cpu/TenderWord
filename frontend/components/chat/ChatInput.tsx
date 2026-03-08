'use client';

import React, { useState, useRef, useCallback } from 'react';
import { ArrowUp, Loader2 } from 'lucide-react';
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
        <div className="flex flex-col gap-3">
          <div>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              disabled={inputLocked}
              rows={1}
              className={cn(
                'block w-full resize-none bg-transparent px-2 py-2.5 text-[15px] leading-6 text-slate-800 transition-colors duration-200 placeholder:text-slate-400 focus:outline-none',
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
          </div>

          <div className="flex items-end justify-between px-2 pb-0.5">
            <ChatModelPicker
              value={selectedModel}
              onChange={onModelChange}
              disabled={inputLocked}
              triggerClassName={cn(
                'h-10 rounded-[18px] bg-slate-50/90 px-4 py-0 shadow-sm shadow-slate-200/70',
                !inputLocked && 'hover:bg-white'
              )}
              menuClassName="left-0 right-auto"
            />

            <div className="flex shrink-0 items-center">
              <button
                type="button"
                onClick={handleSend}
                disabled={isEmpty || inputLocked}
                aria-label={loading ? '发送中' : '发送消息'}
                className={cn(
                  'flex h-10 w-10 items-center justify-center rounded-[18px] border transition-all duration-200',
                  isEmpty || inputLocked
                    ? 'cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400'
                    : 'border-blue-500 bg-blue-500 text-white shadow-sm shadow-blue-200 hover:-translate-y-0.5 hover:bg-blue-600'
                )}
              >
                {loading ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <ArrowUp className="h-5 w-5" strokeWidth={2.4} />
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ChatInput;
