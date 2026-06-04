'use client';

import React, { useRef, useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowUp, FileText, Loader2, Plus, Square, X } from 'lucide-react';
import { cn, formatFileSize } from '@/lib/utils';
import type { ModelType } from '@/components/forms/ModelSelector';
import type { ConversationDraftFile } from '@/stores/chatStore';
import type { AgentSkill } from '@/types/api';
import { ChatModelPicker } from './ChatModelPicker';

const MIN_TEXTAREA_HEIGHT = 44;
const MAX_TEXTAREA_HEIGHT = 180;
const AGENT_SKILL_OPTIONS: Array<{
  skill: AgentSkill;
  title: string;
  description: string;
}> = [
  {
    skill: 'rewrite',
    title: 'rewrite',
    description: '基于当前生成文档或上传 Word 文件重写内容',
  },
];

function isAgentSkill(value: unknown): value is AgentSkill {
  return value === 'rewrite';
}

function normalizeSelectedSkills(skills: AgentSkill[] | undefined): AgentSkill[] {
  if (!Array.isArray(skills)) {
    return [];
  }
  return skills.filter(isAgentSkill).slice(0, 1);
}

function parseExplicitSkillPrefix(rawValue: string): { skill: AgentSkill; nextValue: string } | null {
  const match = rawValue.match(/^\s*([$\/])(rewrite)(?=\s|$)\s*/i);
  if (!match) {
    return null;
  }

  const skill = match[2]?.toLowerCase();
  if (!isAgentSkill(skill)) {
    return null;
  }

  return {
    skill,
    nextValue: rawValue.slice(match[0].length),
  };
}

function getSlashSkillQuery(rawValue: string): string | null {
  const match = rawValue.match(/^\s*\/([^\s]*)$/);
  if (!match) {
    return null;
  }
  return match[1]?.toLowerCase() || '';
}

interface ChatInputProps {
  value: string;
  onValueChange: (value: string) => void;
  onSend: (message: string) => boolean | void | Promise<boolean | void>;
  onCancel?: () => void;
  selectedModel: ModelType;
  onModelChange: (model: ModelType) => void;
  actionMode?: 'send' | 'cancel';
  disabled?: boolean;
  placeholder?: string;
  loading?: boolean;
  rewriteFile?: ConversationDraftFile | null;
  onRewriteFileSelect?: (file: File) => void | Promise<void>;
  onRewriteFileRemove?: () => void;
  selectedSkills?: AgentSkill[];
  onSelectedSkillsChange?: (skills: AgentSkill[]) => void;
  sendDisabled?: boolean;
  noticeMessage?: string | null;
}

function isWordDocument(file: File): boolean {
  return /\.(doc|docx)$/i.test(file.name);
}

function isPromiseLike<T>(value: unknown): value is PromiseLike<T> {
  return (
    typeof value === 'object' &&
    value !== null &&
    'then' in value &&
    typeof (value as PromiseLike<T>).then === 'function'
  );
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
  rewriteFile = null,
  onRewriteFileSelect,
  onRewriteFileRemove,
  selectedSkills,
  onSelectedSkillsChange,
  sendDisabled = false,
  noticeMessage,
}: ChatInputProps) {
  const internalTextareaRef = useRef<HTMLTextAreaElement>(null);
  const menuContainerRef = useRef<HTMLDivElement>(null);
  const skillPickerContainerRef = useRef<HTMLDivElement>(null);
  const hiddenRewriteInputRef = useRef<HTMLInputElement>(null);
  const isCancelAction = actionMode === 'cancel';
  const inputDisabled = disabled;
  const controlsLocked = disabled || loading;
  const sendLocked = disabled || loading || isCancelAction || sendDisabled;
  const [menuOpen, setMenuOpen] = useState(false);
  const [skillPickerQuery, setSkillPickerQuery] = useState<string | null>(null);
  const [localNotice, setLocalNotice] = useState<string | null>(null);

  const composerNotice = noticeMessage || localNotice;
  const isRewriteFileMode = !!rewriteFile;
  const normalizedSelectedSkills = useMemo(
    () => normalizeSelectedSkills(selectedSkills),
    [selectedSkills]
  );
  const selectedSkill = normalizedSelectedSkills[0] || null;
  const filteredSkillOptions = useMemo(() => {
    if (skillPickerQuery === null || skillPickerQuery === '') {
      return AGENT_SKILL_OPTIONS;
    }
    return AGENT_SKILL_OPTIONS.filter((option) => option.skill.includes(skillPickerQuery));
  }, [skillPickerQuery]);
  const skillPickerOpen = !controlsLocked && skillPickerQuery !== null;

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
    if (!menuOpen && !skillPickerOpen) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (
        !menuContainerRef.current?.contains(target) &&
        !skillPickerContainerRef.current?.contains(target)
      ) {
        setMenuOpen(false);
        setSkillPickerQuery(null);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMenuOpen(false);
        setSkillPickerQuery(null);
      }
    };

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [menuOpen, skillPickerOpen]);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || sendLocked) return;

    const finalizeSend = (result: boolean | void) => {
      if (result === false) {
        return;
      }
      onValueChange('');
      resetTextareaHeight(internalTextareaRef.current);
    };

    const sendResult = onSend(trimmed);
    if (isPromiseLike<boolean | void>(sendResult)) {
      void sendResult.then(finalizeSend).catch(() => {});
      return;
    }

    finalizeSend(sendResult);
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
    const parsedPrefix = parseExplicitSkillPrefix(target.value);
    if (parsedPrefix) {
      onSelectedSkillsChange?.([parsedPrefix.skill]);
      onValueChange(parsedPrefix.nextValue);
      setSkillPickerQuery(null);
      target.value = parsedPrefix.nextValue;
      syncTextareaHeight(target);
      return;
    }

    const slashQuery = getSlashSkillQuery(target.value);
    setSkillPickerQuery(slashQuery);
    onValueChange(target.value);
    syncTextareaHeight(target);
  };

  const handleSkillSelect = useCallback(
    (skill: AgentSkill) => {
      onSelectedSkillsChange?.([skill]);
      onValueChange('');
      setSkillPickerQuery(null);
      resetTextareaHeight(internalTextareaRef.current);
      internalTextareaRef.current?.focus();
    },
    [onSelectedSkillsChange, onValueChange, resetTextareaHeight]
  );

  const handleSelectedSkillClear = useCallback(() => {
    onSelectedSkillsChange?.([]);
    internalTextareaRef.current?.focus();
  }, [onSelectedSkillsChange]);

  const openRewritePicker = useCallback(() => {
    if (controlsLocked) {
      return;
    }
    setMenuOpen(false);
    hiddenRewriteInputRef.current?.click();
  }, [controlsLocked]);

  const handleRewriteFileChange = useCallback(
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
      await onRewriteFileSelect?.(file);
    },
    [onRewriteFileSelect]
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
            ref={hiddenRewriteInputRef}
            type="file"
            accept=".doc,.docx"
            className="hidden"
            data-testid="chat-rewrite-file-input"
            onChange={handleRewriteFileChange}
          />

          {isRewriteFileMode && rewriteFile ? (
            <div
              className="flex items-start justify-between gap-3 rounded-2xl border border-blue-200/90 bg-blue-50/70 px-3.5 py-3"
              data-testid="chat-rewrite-file-card"
            >
              <div className="flex min-w-0 items-start gap-3">
                <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-white text-blue-600 shadow-sm">
                  <FileText className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-blue-700">
                    <span>上传文件重写</span>
                  </div>
                  <p className="mt-1 truncate text-sm font-semibold text-slate-900">
                    {rewriteFile.original_name}
                  </p>
                  <p className="mt-1 text-xs text-slate-600">
                    {formatFileSize(rewriteFile.size)}
                  </p>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-1.5">
                <button
                  type="button"
                  onClick={openRewritePicker}
                  disabled={controlsLocked}
                  data-testid="chat-rewrite-file-replace"
                  className={cn(
                    'rounded-xl border border-blue-200 bg-white px-3 py-1.5 text-xs font-medium text-blue-700 transition-colors',
                    controlsLocked ? 'cursor-not-allowed opacity-60' : 'hover:bg-blue-100/60'
                  )}
                >
                  更换
                </button>
                <button
                  type="button"
                  onClick={onRewriteFileRemove}
                  disabled={controlsLocked}
                  data-testid="chat-rewrite-file-remove"
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

          {selectedSkill ? (
            <div className="flex items-center gap-2 px-2" data-testid="chat-selected-skill-row">
              <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                已选能力
              </span>
              <div
                className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700"
                data-testid={`chat-selected-skill-${selectedSkill}`}
              >
                <span>{selectedSkill}</span>
                <button
                  type="button"
                  onClick={handleSelectedSkillClear}
                  disabled={controlsLocked}
                  aria-label="清除已选能力"
                  data-testid="chat-selected-skill-clear"
                  className={cn(
                    'inline-flex h-4 w-4 items-center justify-center rounded-full text-emerald-700 transition-colors',
                    controlsLocked ? 'cursor-not-allowed opacity-60' : 'hover:bg-emerald-100'
                  )}
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            </div>
          ) : null}

          <div ref={skillPickerContainerRef} className="relative">
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

            {skillPickerOpen ? (
              <div
                className="absolute bottom-full left-2 right-2 z-30 mb-2 overflow-hidden rounded-[22px] border border-slate-200 bg-white/96 p-2 shadow-2xl shadow-slate-300/30 backdrop-blur"
                data-testid="chat-skill-picker"
              >
                {filteredSkillOptions.map((option) => {
                  const isSelected = option.skill === selectedSkill;
                  return (
                    <button
                      key={option.skill}
                      type="button"
                      onClick={() => handleSkillSelect(option.skill)}
                      data-testid={`chat-skill-option-${option.skill}`}
                      className={cn(
                        'flex w-full items-start gap-3 rounded-2xl border px-3.5 py-3 text-left transition-colors',
                        isSelected
                          ? 'border-emerald-200 bg-emerald-50/80'
                          : 'border-transparent bg-slate-50/80 hover:border-blue-200 hover:bg-blue-50/70'
                      )}
                    >
                      <div className="flex min-w-0 flex-1 flex-col">
                        <span className="text-sm font-semibold text-slate-900">{option.title}</span>
                        <span className="mt-1 text-xs leading-5 text-slate-600">
                          {option.description}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            ) : null}
          </div>

          <div className="flex items-end justify-between gap-3 px-2 pb-0.5">
            <div className="flex items-center gap-2">
              <div ref={menuContainerRef} className="relative">
                <button
                  type="button"
                  onClick={() => setMenuOpen((current) => !current)}
                  disabled={controlsLocked}
                  aria-label={loading ? '更多操作处理中' : '打开更多操作'}
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
                  {loading ? (
                    <Loader2
                      data-testid="chat-plus-loading-icon"
                      className="h-4 w-4 animate-spin"
                    />
                  ) : (
                    <Plus className="h-4 w-4" />
                  )}
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
                      onClick={openRewritePicker}
                      data-testid="chat-plus-menu-rewrite-file"
                      className="flex w-full items-start gap-3 rounded-2xl border border-transparent bg-slate-50/80 px-3.5 py-3 text-left transition-colors hover:border-blue-200 hover:bg-blue-50/70"
                    >
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-white text-blue-600 shadow-sm">
                        <FileText className="h-5 w-5" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-slate-900">上传文件重写</p>
                        <p className="mt-1 text-xs leading-5 text-slate-600">
                          上传一个 Word 文档，并按输入要求重写当前锚点区正文。
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
