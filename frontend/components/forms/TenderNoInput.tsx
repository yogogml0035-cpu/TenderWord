'use client';

import React, { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { Search, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { fetchTenderData as apiFetchTenderData, ApiError } from '@/lib/api';
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
  placeholder = '请输入招标编号，如：ZBGG-2024-001',
  required = false,
  disabled = false,
  className,
}: TenderNoInputProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [fetchedData, setFetchedData] = useState<TenderData | null>(null);

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

      setFetchedData(data);
      setSuccess(true);
      onDataFetched?.(data);
    } catch (err) {
      const errorMessage = err instanceof ApiError ? err.message : (err instanceof Error ? err.message : '获取招标数据失败');
      setError(errorMessage);
      setFetchedData(null);
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
    <div className={cn('space-y-2', className)}>
      <label className="block text-sm font-medium text-[var(--foreground)]">
        {label}
        {required && <span className="text-[var(--error)] ml-1">*</span>}
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
              'input-field w-full pr-10',
              error && 'border-[var(--error)] focus:ring-[var(--error)]',
              success && 'border-[var(--success)] focus:ring-[var(--success)]'
            )}
          />
          {success && (
            <CheckCircle className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[var(--success)]" />
          )}
          {error && !isLoading && (
            <AlertCircle className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[var(--error)]" />
          )}
        </div>
        <button
          type="button"
          onClick={handleFetchData}
          disabled={disabled || isLoading || !value.trim()}
          className="btn-secondary whitespace-nowrap"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <>
              <Search className="w-4 h-4 mr-1" />
              获取信息
            </>
          )}
        </button>
      </div>

      {error && (
        <p className="text-sm text-[var(--error)] flex items-center gap-1">
          <AlertCircle className="w-4 h-4" />
          {error}
        </p>
      )}

      {success && fetchedData && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-md">
          <p className="text-sm text-green-800 font-medium">{fetchedData.project_name}</p>
          <p className="text-xs text-green-600 mt-1">
            采购人：{fetchedData.buyer_name}
          </p>
        </div>
      )}
    </div>
  );
}

export default TenderNoInput;
