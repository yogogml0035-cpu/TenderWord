'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import { Cpu, Brain, Zap } from 'lucide-react';

export type ModelType = 'deepseek' | 'qwen' | 'doubao';

export interface ModelOption {
  value: ModelType;
  label: string;
  description: string;
  icon: React.ReactNode;
  recommended?: boolean;
}

export const MODEL_OPTIONS: ModelOption[] = [
  {
    value: 'deepseek',
    label: 'DeepSeek',
    description: '深度求索大模型，擅长长文本理解',
    icon: <Brain className="w-5 h-5" />,
    recommended: true,
  },
  {
    value: 'qwen',
    label: '通义千问',
    description: '阿里云通义千问，中文理解能力强',
    icon: <Cpu className="w-5 h-5" />,
  },
  {
    value: 'doubao',
    label: '豆包',
    description: '字节跳动豆包模型，响应速度快',
    icon: <Zap className="w-5 h-5" />,
  },
];

export interface ModelSelectorProps {
  value: ModelType;
  onChange: (value: ModelType) => void;
  label?: string;
  required?: boolean;
  disabled?: boolean;
  className?: string;
  showCards?: boolean;
}

export function ModelSelector({
  value,
  onChange,
  label = '选择模型',
  required = false,
  disabled = false,
  className,
  showCards = true,
}: ModelSelectorProps) {
  if (showCards) {
    return (
      <div className={cn('space-y-3', className)}>
        <label className="block text-sm font-medium text-[var(--foreground)]">
          {label}
          {required && <span className="text-[var(--error)] ml-1">*</span>}
        </label>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {MODEL_OPTIONS.map((model) => (
            <button
              key={model.value}
              type="button"
              onClick={() => !disabled && onChange(model.value)}
              disabled={disabled}
              className={cn(
                'relative p-4 border rounded-lg text-left transition-all',
                value === model.value
                  ? 'border-[var(--primary)] bg-[var(--primary)]/5 ring-1 ring-[var(--primary)]'
                  : 'border-[var(--border)] hover:border-[var(--primary)]/50 hover:bg-gray-50',
                disabled && 'opacity-50 cursor-not-allowed'
              )}
            >
              {model.recommended && (
                <span className="absolute -top-2 -right-2 px-2 py-0.5 bg-[var(--primary)] text-white text-xs font-medium rounded-full">
                  推荐
                </span>
              )}
              <div className="flex items-start gap-3">
                <div
                  className={cn(
                    'p-2 rounded-lg',
                    value === model.value
                      ? 'bg-[var(--primary)]/10 text-[var(--primary)]'
                      : 'bg-[var(--secondary-bg)] text-[var(--text-muted)]'
                  )}
                >
                  {model.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <p
                    className={cn(
                      'font-medium',
                      value === model.value
                        ? 'text-[var(--primary)]'
                        : 'text-[var(--foreground)]'
                    )}
                  >
                    {model.label}
                  </p>
                  <p className="text-xs text-[var(--text-muted)] mt-0.5">
                    {model.description}
                  </p>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>
    );
  }

  // Simple select version
  return (
    <div className={cn('space-y-2', className)}>
      <label className="block text-sm font-medium text-[var(--foreground)]">
        {label}
        {required && <span className="text-[var(--error)] ml-1">*</span>}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as ModelType)}
        disabled={disabled}
        className="select-field w-full"
      >
        {MODEL_OPTIONS.map((model) => (
          <option key={model.value} value={model.value}>
            {model.label} {model.recommended ? '（推荐）' : ''}
          </option>
        ))}
      </select>
    </div>
  );
}

export default ModelSelector;
