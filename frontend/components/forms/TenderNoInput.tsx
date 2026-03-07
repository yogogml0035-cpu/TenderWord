'use client';

import React, { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { Search, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { fetchTenderData as apiFetchTenderData, ApiError } from '@/lib/api';
import { generateConversationTitle } from '@/lib/chat-utils';
import { useChatStore } from '@/stores/chatStore';
import type { TenderData } from '@/types/api';

// Re-export TenderData for backward compatibility
export type { TenderData };

export interface TenderNoInputProps {
  value: string;
  onChange: (value: string) => void;
  onDataFetched?: (data: TenderData) => void;
  label?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  className?: string;
}

export function TenderNoInput({
  value,
  onChange,
  onDataFetched,
  label = '招标编号',
  placeholder = '请输入招标编号，如：0811-DSITC26xxxx',
  required = false,
  disabled = false,
  className,
}: TenderNoInputProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleFetchData = useCallback(async () => {
    if (!value.trim()) {
      setError('请输入招标编号');
      return;
    }

    setIsLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const data = await apiFetchTenderData(value.trim());

      setSuccess(true);

      // Update conversation title when data fetch succeeds
      const { currentConversationId, updateConversation } = useChatStore.getState();
      if (currentConversationId) {
        const newTitle = generateConversationTitle(value.trim());
        updateConversation(currentConversationId, { title: newTitle });
      }

      onDataFetched?.(data);
    } catch (err) {
      const errorMessage =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : '获取招标数据失败';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [value, onDataFetched]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleFetchData();
      }
    },
    [handleFetchData]
  );

  return (
    <div className={cn('space-y-1.5', className)}>
      <label className="block text-sm font-semibold text-[var(--foreground)]">
        {label}
        {required && <span className="ml-1 text-[var(--error)]">*</span>}
      </label>

      <div className="flex gap-2">
        <div className="relative flex-1">
          <input
            type="text"
            value={value}
            onChange={(e) => {
              onChange(e.target.value);
              setError(null);
              setSuccess(false);
            }}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled || isLoading}
            className={cn(
              'input-field h-11 w-full rounded-xl px-3.5 pr-10 text-sm',
              error && 'border-[var(--error)] focus:ring-[var(--error)]',
              success && 'border-[var(--success)] focus:ring-[var(--success)]'
            )}
          />
          {success && (
            <CheckCircle className="absolute top-1/2 right-3 h-4.5 w-4.5 -translate-y-1/2 text-[var(--success)]" />
          )}
          {error && !isLoading && (
            <AlertCircle className="absolute top-1/2 right-3 h-4.5 w-4.5 -translate-y-1/2 text-[var(--error)]" />
          )}
        </div>
        <button
          type="button"
          onClick={handleFetchData}
          disabled={disabled || isLoading || !value.trim()}
          className={cn(
            'inline-flex h-11 shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-xl border border-[var(--border)] bg-[var(--secondary-bg)] px-4 text-sm font-semibold text-[var(--foreground)] transition-all',
            'hover:border-[var(--primary)]/20 hover:bg-slate-100',
            'focus:ring-2 focus:ring-[var(--primary)]/15 focus:outline-none',
            'disabled:cursor-not-allowed disabled:opacity-50'
          )}
        >
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <Search className="h-4 w-4" />
              获取信息
            </>
          )}
        </button>
      </div>

      {error && (
        <p className="flex items-center gap-1 text-xs text-[var(--error)]">
          <AlertCircle className="h-3.5 w-3.5" />
          {error}
        </p>
      )}

    </div>
  );
}

export default TenderNoInput;
