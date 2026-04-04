'use client';

import React, { useRef, useCallback, useEffect, useState } from 'react';
import { ArrowUp, FileText, Loader2, Plus, Square, X } from 'lucide-react';
import { cn, formatFileSize } from '@/lib/utils';
import type { ModelType } from '@/components/forms/ModelSelector';
import type { ConversationDraftFile } from '@/stores/chatStore';
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
  actionMode?: 'send' | 'cancel';
  disabled?: boolean;
  placeholder?: string;
  loading?: boolean;
  inputMode?: 'normal' | 'edit';
  editFile?: ConversationDraftFile | null;
  onEditFileSelect?: (file: File) => void | Promise<void>;
  onEditFileRemove?: () => void;
  sendDisabled?: boolean;
  noticeMessage?: string | null;
}

function isWordDocument(file: File): boolean {
  return /\.(doc|docx)$/i.test(file.name);
}

export function ChatInput({
  value,
  onValueChange,
  onSend,
  onCancel,
  selectedModel,
  onModelChange,
  actionMode = 'send',
  disabled = false,
  placeholder = '输入文字并发送即可对话...',
  loading = false,
  inputMode = 'normal',
  editFile = null,
  onEditFileSelect,
  onEditFileRemove,
  sendDisabled = false,
  noticeMessage,
}: ChatInputProps) {
  const internalTextareaRef = useRef<HTMLTextAreaElement>(null);
  const menuContainerRef = useRef<HTMLDivElement>(null);
  const hiddenEditInputRef = useRef<HTMLInputElement>(null);
  const isCancelAction = actionMode === 'cancel';
  const inputDisabled = disabled;
  const controlsLocked = disabled || loading;
  const sendLocked = disabled || loading || isCancelAction || sendDisabled;
  const [menuOpen, setMenuOpen] = useState(false);
  const [localNotice, setLocalNotice] = useState<string | null>(null);

  const composerNotice = noticeMessage || localNotice;
  const isEditMode = inputMode === 'edit';

  const syncTextareaHeight = useCallback((textarea: HTMLTextAreaElement | null) => {
    if (!textarea) {
      return;
    }

    textarea.style.height = '0px';

    const nextHeight = Math.min(
      Math.max(textarea.scrollHeight, MIN_TEXTAREA_HEIGHT),
      MAX_TEXTAREA_HEIGHT
    );

    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY = textarea.scrollHeight > MAX_TEXTAREA_HEIGHT ? 'auto' : 'hidden';
  }, []);

  const resetTextareaHeight = useCallback((textarea: HTMLTextAreaElement | null) => {
    if (!textarea) {
      return;
    }

    textarea.style.height = `${MIN_TEXTAREA_HEIGHT}px`;
    textarea.style.overflowY = 'hidden';
    textarea.scrollTop = 0;
  }, []);

  useEffect(() => {
    syncTextareaHeight(internalTextareaRef.current);
  }, [syncTextareaHeight, value]);

  useEffect(() => {
    if (!menuOpen) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      if (!menuContainerRef.current?.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMenuOpen(false);
      }
    };

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [menuOpen]);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || sendLocked) return;

    onSend(trimmed);
    onValueChange('');
    resetTextareaHeight(internalTextareaRef.current);
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
    syncTextareaHeight(target);
  };

  const openEditPicker = useCallback(() => {
    if (controlsLocked) {
      return;
    }
    setMenuOpen(false);
    hiddenEditInputRef.current?.click();
  }, [controlsLocked]);

  const handleEditFileChange = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      event.target.value = '';
      if (!file) {
        return;
      }
      if (!isWordDocument(file)) {
        setLocalNotice('仅支持上传 .doc 或 .docx 文件');
        return;
      }
      setLocalNotice(null);
      await onEditFileSelect?.(file);
    },
    [onEditFileSelect]
  );

  const isEmpty = !value.trim();

  return (
    <div className="border-t border-slate-200/80 bg-gradient-to-b from-white via-slate-50/80 to-white px-4 py-3">
      <div
        className={cn(
          'rounded-[28px] border-2 border-slate-300/80 bg-gradient-to-br from-white via-white to-slate-50/80 px-3 py-3 shadow-[0_18px_40px_-24px_rgba(15,23,42,0.45)] ring-1 ring-white/90 transition-all duration-200 focus-within:-translate-y-0.5 focus-within:border-blue-400/90 focus-within:shadow-[0_24px_50px_-24px_rgba(59,130,246,0.35)] focus-within:ring-4 focus-within:ring-blue-100/80',
          controlsLocked && 'opacity-95'
        )}
      >
        <div className="flex flex-col gap-3">
          <input
            ref={hiddenEditInputRef}
            type="file"
            accept=".doc,.docx"
            className="hidden"
            data-testid="chat-edit-file-input"
            onChange={handleEditFileChange}
          />

          {isEditMode && editFile ? (
            <div
              className="flex items-start justify-between gap-3 rounded-2xl border border-blue-200/90 bg-blue-50/70 px-3.5 py-3"
              data-testid="chat-edit-file-card"
            >
              <div className="flex min-w-0 items-start gap-3">
                <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-white text-blue-600 shadow-sm">
                  <FileText className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-blue-700">
                    <span>上传文件修改</span>
                  </div>
                  <p className="mt-1 truncate text-sm font-semibold text-slate-900">
                    {editFile.original_name}
                  </p>
                  <p className="mt-1 text-xs text-slate-600">
                    {formatFileSize(editFile.size)}
                  </p>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-1.5">
                <button
                  type="button"
                  onClick={openEditPicker}
                  disabled={controlsLocked}
                  data-testid="chat-edit-file-replace"
                  className={cn(
                    'rounded-xl border border-blue-200 bg-white px-3 py-1.5 text-xs font-medium text-blue-700 transition-colors',
                    controlsLocked ? 'cursor-not-allowed opacity-60' : 'hover:bg-blue-100/60'
                  )}
                >
                  更换
                </button>
                <button
                  type="button"
                  onClick={onEditFileRemove}
                  disabled={controlsLocked}
                  data-testid="chat-edit-file-remove"
                  className={cn(
                    'flex h-8 w-8 items-center justify-center rounded-xl border border-blue-200 bg-white text-slate-500 transition-colors',
                    controlsLocked ? 'cursor-not-allowed opacity-60' : 'hover:bg-blue-100/60'
                  )}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
          ) : null}

          <div>
            <textarea
              ref={internalTextareaRef}
              value={value}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              disabled={inputDisabled}
              rows={1}
              className={cn(
                'block w-full resize-none bg-transparent px-2 py-2.5 text-[15px] leading-6 text-slate-800 transition-colors duration-200 placeholder:text-slate-500/90 focus:outline-none',
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

          <div className="flex items-end justify-between gap-3 px-2 pb-0.5">
            <div className="flex items-center gap-2">
              <div ref={menuContainerRef} className="relative">
                <button
                  type="button"
                  onClick={() => setMenuOpen((current) => !current)}
                  disabled={controlsLocked}
                  aria-expanded={menuOpen}
                  aria-haspopup="menu"
                  data-testid="chat-plus-trigger"
                  className={cn(
                    'flex h-10 w-10 items-center justify-center rounded-[18px] border border-slate-200 bg-white text-slate-600 shadow-sm transition-all duration-200',
                    controlsLocked
                      ? 'cursor-not-allowed opacity-60'
                      : 'hover:border-blue-200 hover:bg-blue-50/70 hover:text-blue-700'
                  )}
                >
                  <Plus className="h-4 w-4" />
                </button>

                {menuOpen && !controlsLocked ? (
                  <div
                    role="menu"
                    data-testid="chat-plus-menu"
                    className="absolute bottom-full left-0 z-30 mb-3 w-64 overflow-hidden rounded-[24px] border border-slate-200 bg-white/96 p-2 shadow-2xl shadow-slate-300/30 backdrop-blur"
                  >
                    <button
                      type="button"
                      role="menuitem"
                      onClick={openEditPicker}
                      data-testid="chat-plus-menu-edit"
                      className="flex w-full items-start gap-3 rounded-2xl border border-transparent bg-slate-50/80 px-3.5 py-3 text-left transition-colors hover:border-blue-200 hover:bg-blue-50/70"
                    >
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-white text-blue-600 shadow-sm">
                        <FileText className="h-5 w-5" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-slate-900">上传文件修改</p>
                        <p className="mt-1 text-xs leading-5 text-slate-600">
                          上传一个 Word 文档，并按输入要求只修改当前锚点区正文。
                        </p>
                      </div>
                    </button>
                  </div>
                ) : null}
              </div>

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
            </div>

            <div className="flex shrink-0 items-center">
              <button
                type="button"
                onClick={isCancelAction ? handleCancel : handleSend}
                disabled={isCancelAction ? !onCancel : isEmpty || sendLocked}
                aria-label={isCancelAction ? '暂停任务' : loading ? '发送中' : '发送消息'}
                data-testid="chat-send-button"
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

          {composerNotice ? (
            <p
              className="px-2 text-xs leading-5 text-amber-700"
              data-testid="chat-input-notice"
            >
              {composerNotice}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default ChatInput;
