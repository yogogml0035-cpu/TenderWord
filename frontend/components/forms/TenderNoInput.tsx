'use client';

import React, { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { Search, Loader2, CheckCircle, AlertCircle } from 'lucide-react';

export interface TenderData {
  project_name: string;
  project_number: string;
  project_content: string;
  bzj_rule: string;
  buyer_name: string;
  project_zbr_xbr: string;
  zbr_xbr_tel: string;
  zbr_pinyin: string;
  shell_start_date: string;
  shell_end_date: string;
  submit_date: string;
  platform: string;
  service_fee: string;
}

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

  const fetchTenderData = useCallback(async () => {
    if (!value.trim()) {
      setError('请输入招标编号');
      return;
    }

    setIsLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const response = await fetch(`/api/tender/${encodeURIComponent(value.trim())}`);
      const result = await response.json();

      if (!response.ok || !result.success) {
        throw new Error(result.error?.message || '获取招标数据失败');
      }

      setFetchedData(result.data);
      setSuccess(true);
      onDataFetched?.(result.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取招标数据失败');
      setFetchedData(null);
    } finally {
      setIsLoading(false);
    }
  }, [value, onDataFetched]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        fetchTenderData();
      }
    },
    [fetchTenderData]
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
              'st-input w-full pr-10',
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
          onClick={fetchTenderData}
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
