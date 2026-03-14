'use client';

import React, { useCallback } from 'react';
import { cn } from '@/lib/utils';
import { Search, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import type { TenderData } from '@/types/api';

// Re-export TenderData for backward compatibility
export type { TenderData };

export interface TenderNoInputProps {
  value: string;
  onChange: (value: string) => void;
  onFetch?: () => Promise<unknown> | void;
  label?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  className?: string;
  isLoading?: boolean;
  isSuccess?: boolean;
  error?: string | null;
}

export function TenderNoInput({
  value,
  onChange,
  onFetch,
  label = '招标编号',
  placeholder = '请输入招标编号，如：0811-DSITC26xxxx',
  required = false,
  disabled = false,
  className,
  isLoading = false,
  isSuccess = false,
  error = null,
}: TenderNoInputProps) {
  const handleFetchData = useCallback(async () => {
    if (!value.trim() || !onFetch) {
      return;
    }

    await onFetch();
  }, [onFetch, value]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && value.trim()) {
        e.preventDefault();
        void handleFetchData();
      }
    },
    [handleFetchData, value]
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
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled || isLoading}
            aria-invalid={error ? 'true' : 'false'}
            className={cn(
              'input-field h-11 w-full rounded-xl px-3.5 pr-10 text-sm',
              error && 'border-[var(--error)] focus:ring-[var(--error)]',
              isSuccess && 'border-[var(--success)] focus:ring-[var(--success)]'
            )}
          />
          {isSuccess && !error && !isLoading && (
            <CheckCircle
              data-testid="tender-no-success-icon"
              className="absolute top-1/2 right-3 h-4.5 w-4.5 -translate-y-1/2 text-[var(--success)]"
            />
          )}
          {error && !isLoading && (
            <AlertCircle
              data-testid="tender-no-error-icon"
              className="absolute top-1/2 right-3 h-4.5 w-4.5 -translate-y-1/2 text-[var(--error)]"
            />
          )}
        </div>
        <button
          type="button"
          onClick={() => void handleFetchData()}
          disabled={disabled || isLoading || !value.trim() || !onFetch}
          className={cn(
            'inline-flex h-11 shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-xl border border-[var(--border)] bg-[var(--secondary-bg)] px-4 text-sm font-semibold text-[var(--foreground)] transition-all',
            'hover:border-[var(--primary)]/20 hover:bg-slate-100',
            'focus:ring-2 focus:ring-[var(--primary)]/15 focus:outline-none',
            'disabled:cursor-not-allowed disabled:opacity-50'
          )}
        >
          {isLoading ? (
            <Loader2 data-testid="tender-no-loading-icon" className="h-4 w-4 animate-spin" />
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
