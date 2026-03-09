'use client';

import React, { useRef, useCallback } from 'react';
import { ArrowUp, Languages, Loader2, Square, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ModelType } from '@/components/forms/ModelSelector';
import { ChatModelPicker } from './ChatModelPicker';

const MIN_TEXTAREA_HEIGHT = 44;
const MAX_TEXTAREA_HEIGHT = 180;

interface ChatInputProps {
  value: string;
  onValueChange: (value: string) => void;
  onSend: (message: string) => void;
  onCancel?: () => void;
  selectedModel: ModelType;
  onModelChange: (model: ModelType) => void;
  chatMode?: 'normal' | 'rewrite';
  onToggleRewriteMode?: () => void;
  rewriteAvailable?: boolean;
  rewriteHint?: string | null;
  actionMode?: 'send' | 'cancel';
  disabled?: boolean;
  placeholder?: string;
  loading?: boolean;
}

export function ChatInput({
  value,
  onValueChange,
  onSend,
  onCancel,
  selectedModel,
  onModelChange,
  chatMode = 'normal',
  onToggleRewriteMode,
  rewriteAvailable = false,
  rewriteHint,
  actionMode = 'send',
  disabled = false,
  placeholder = '输入消息...',
  loading = false,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const rewriteModeEnabled = chatMode === 'rewrite';
  const rewriteButtonDisabled = !rewriteModeEnabled && !rewriteAvailable;
  const isCancelAction = actionMode === 'cancel';
  const inputDisabled = disabled;
  const controlsLocked = disabled || loading;
  const sendLocked = disabled || loading || isCancelAction;

  const resetTextareaHeight = useCallback((textarea: HTMLTextAreaElement | null) => {
    if (!textarea) {
      return;
    }

    textarea.style.height = `${MIN_TEXTAREA_HEIGHT}px`;
    textarea.style.overflowY = 'hidden';
    textarea.scrollTop = 0;
  }, []);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || sendLocked) return;

    onSend(trimmed);
    onValueChange('');
    resetTextareaHeight(textareaRef.current);
  }, [onSend, onValueChange, resetTextareaHeight, sendLocked, value]);

  const handleCancel = useCallback(() => {
    onCancel?.();
  }, [onCancel]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const target = e.target;
    onValueChange(target.value);

    target.style.height = '0px';

    const nextHeight = Math.min(
      Math.max(target.scrollHeight, MIN_TEXTAREA_HEIGHT),
      MAX_TEXTAREA_HEIGHT
    );

    target.style.height = `${nextHeight}px`;
    target.style.overflowY = target.scrollHeight > MAX_TEXTAREA_HEIGHT ? 'auto' : 'hidden';
  };

  const isEmpty = !value.trim();

  return (
    <div className="border-t border-slate-200 bg-gradient-to-b from-white via-slate-50/60 to-white px-4 py-2.5">
      <div
        className={cn(
          'rounded-[26px] border border-slate-200 bg-white px-3 py-2.5 shadow-lg shadow-slate-200/70 transition-all duration-200',
          controlsLocked && 'opacity-90'
        )}
      >
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between px-2">
            <button
              type="button"
              onClick={onToggleRewriteMode}
              disabled={rewriteButtonDisabled}
              className={cn(
                'group inline-flex h-9 items-center gap-1.5 rounded-full px-3.5 text-sm font-medium transition-all duration-200',
                rewriteModeEnabled
                  ? 'border border-blue-100 bg-blue-50 text-blue-700 shadow-sm shadow-blue-100/70'
                  : 'border border-slate-200 bg-white text-slate-600 hover:border-blue-200 hover:bg-blue-50/60 hover:text-blue-700',
                rewriteButtonDisabled && 'cursor-not-allowed opacity-45'
              )}
            >
              <Languages className="h-4 w-4 shrink-0" strokeWidth={2.1} />
              <span className="leading-none">修改润色</span>
              {rewriteModeEnabled && (
                <X
                  className="h-3.5 w-3.5 shrink-0 opacity-80 transition-opacity group-hover:opacity-100"
                  strokeWidth={2.4}
                />
              )}
            </button>
            {rewriteHint ? <span className="text-xs text-amber-600">{rewriteHint}</span> : <span />}
          </div>

          <div>
            <textarea
              ref={textareaRef}
              value={value}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              disabled={inputDisabled}
              rows={1}
              className={cn(
                'block w-full resize-none bg-transparent px-2 py-2.5 text-[15px] leading-6 text-slate-800 transition-colors duration-200 placeholder:text-slate-400 focus:outline-none',
                inputDisabled && 'cursor-not-allowed text-slate-500'
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
              disabled={controlsLocked}
              triggerClassName={cn(
                'h-10 rounded-[18px] bg-slate-50/90 px-4 py-0 shadow-sm shadow-slate-200/70',
                !controlsLocked && 'hover:bg-white'
              )}
              menuClassName="left-0 right-auto"
            />

            <div className="flex shrink-0 items-center">
              <button
                type="button"
                onClick={isCancelAction ? handleCancel : handleSend}
                disabled={isCancelAction ? !onCancel : isEmpty || sendLocked}
                aria-label={isCancelAction ? '暂停任务' : loading ? '发送中' : '发送消息'}
                className={cn(
                  'flex h-10 w-10 items-center justify-center rounded-[18px] border transition-all duration-200',
                  isCancelAction
                    ? 'border-blue-500 bg-blue-500 text-white shadow-sm shadow-blue-200 hover:-translate-y-0.5 hover:bg-blue-600'
                    : isEmpty || sendLocked
                      ? 'cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400'
                      : 'border-blue-500 bg-blue-500 text-white shadow-sm shadow-blue-200 hover:-translate-y-0.5 hover:bg-blue-600'
                )}
              >
                {isCancelAction ? (
                  <Square className="h-5 w-5 fill-current" />
                ) : loading ? (
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
