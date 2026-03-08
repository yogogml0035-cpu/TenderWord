'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import { Cpu, Brain, Zap } from 'lucide-react';

export type ModelType = 'deepseek' | 'qwen' | 'doubao';

export interface ModelOption {
  value: ModelType;
  label: string;
  description: string;
  detail: string;
  badge: string;
  icon: React.ReactNode;
  recommended?: boolean;
}

export const MODEL_OPTIONS: ModelOption[] = [
  {
    value: 'deepseek',
    label: 'DeepSeek',
    description: '深度推理与长文本生成',
    detail: '适合复杂条款分析、结构化写作和长篇内容扩写。',
    badge: '默认推荐',
    icon: <Brain className="h-5 w-5" />,
    recommended: true,
  },
  {
    value: 'qwen',
    label: '通义千问',
    description: '中文理解稳定，表达更均衡',
    detail: '适合商务措辞优化、条文总结和通用问答。',
    badge: '均衡通用',
    icon: <Cpu className="h-5 w-5" />,
  },
  {
    value: 'doubao',
    label: '豆包',
    description: '响应更快，轻量交互顺手',
    detail: '适合快速追问、短内容生成和改写润色。',
    badge: '快速响应',
    icon: <Zap className="h-5 w-5" />,
  },
];

export function getModelOption(value: ModelType): ModelOption {
  return MODEL_OPTIONS.find((model) => model.value === value) ?? MODEL_OPTIONS[0];
}

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
      <div className={cn('space-y-2.5', className)}>
        <label className="block text-sm font-semibold text-[var(--foreground)]">
          {label}
          {required && <span className="ml-1 text-[var(--error)]">*</span>}
        </label>

        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
          {MODEL_OPTIONS.map((model) => (
            <button
              key={model.value}
              type="button"
              onClick={() => !disabled && onChange(model.value)}
              disabled={disabled}
              className={cn(
                'relative min-h-[96px] overflow-hidden rounded-xl border px-3.5 py-3 text-left transition-all',
                value === model.value
                  ? 'border-[var(--primary)] bg-[var(--primary)]/5 shadow-sm ring-1 ring-[var(--primary)]/30'
                  : 'border-[var(--border)] bg-white hover:border-[var(--primary)]/40 hover:bg-slate-50',
                disabled && 'cursor-not-allowed opacity-50'
              )}
            >
              <div className="flex items-start gap-2.5">
                <div
                  className={cn(
                    'rounded-xl p-2.5',
                    value === model.value
                      ? 'bg-[var(--primary)]/10 text-[var(--primary)]'
                      : 'bg-[var(--secondary-bg)] text-[var(--text-muted)]'
                  )}
                >
                  {model.icon}
                </div>
                <div className="min-w-0 flex-1">
                  <p
                    className={cn(
                      'text-base font-semibold',
                      value === model.value ? 'text-[var(--primary)]' : 'text-[var(--foreground)]'
                    )}
                  >
                    {model.label}
                  </p>
                  <p className="mt-1 text-[13px] leading-5 text-[var(--text-muted)]">
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
      <label className="block text-sm font-semibold text-[var(--foreground)]">
        {label}
        {required && <span className="ml-1 text-[var(--error)]">*</span>}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as ModelType)}
        disabled={disabled}
        className="select-field w-full"
      >
        {MODEL_OPTIONS.map((model) => (
          <option key={model.value} value={model.value}>
            {model.label}
          </option>
        ))}
      </select>
    </div>
  );
}

export default ModelSelector;
