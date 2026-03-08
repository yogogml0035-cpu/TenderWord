'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import {
  getModelOption,
  MODEL_OPTIONS,
  type ModelType,
} from '@/components/forms/ModelSelector';
import { cn } from '@/lib/utils';

interface ChatModelPickerProps {
  value: ModelType;
  onChange: (value: ModelType) => void;
  disabled?: boolean;
}

export function ChatModelPicker({
  value,
  onChange,
  disabled = false,
}: ChatModelPickerProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const selectedOption = getModelOption(value);
  const isOpen = open && !disabled;

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        disabled={disabled}
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        aria-label="选择聊天模型"
        data-testid="chat-model-trigger"
        className={cn(
          'group inline-flex max-w-full items-center gap-2 rounded-2xl border border-slate-200 bg-white/95 px-3.5 py-2 text-left shadow-sm transition-all duration-200',
          disabled
            ? 'cursor-not-allowed opacity-60'
            : 'hover:border-blue-200 hover:bg-white hover:shadow-md'
        )}
      >
        <div className="flex min-w-0 flex-col">
          <span className="text-[11px] font-medium tracking-[0.18em] text-slate-400 uppercase">
            模型
          </span>
          <span className="truncate text-sm font-semibold text-slate-900">{selectedOption.label}</span>
        </div>
        <ChevronDown
          className={cn(
            'h-4 w-4 shrink-0 text-slate-400 transition-transform duration-200',
            isOpen && 'rotate-180'
          )}
        />
      </button>

      {isOpen && (
        <div
          role="dialog"
          aria-label="选择聊天模型"
          className="animate-scale-in absolute bottom-full left-0 z-30 mb-3 w-[min(26rem,calc(100vw-3rem))] overflow-hidden rounded-[28px] border border-slate-200 bg-white/96 shadow-2xl shadow-slate-300/40 backdrop-blur"
        >
          <div className="border-b border-slate-100 bg-gradient-to-r from-slate-50 via-white to-blue-50/60 px-5 py-4">
            <p className="text-base font-semibold text-slate-900">选择当前聊天模型</p>
            <p className="mt-1 text-sm text-slate-500">
              当前项目已配置 3 个模型，可按推理深度和响应速度切换。
            </p>
          </div>

          <div className="space-y-2 p-2.5">
            {MODEL_OPTIONS.map((model) => {
              const isActive = model.value === value;

              return (
                <button
                  key={model.value}
                  type="button"
                  onClick={() => {
                    onChange(model.value);
                    setOpen(false);
                  }}
                  data-testid={`chat-model-option-${model.value}`}
                  className={cn(
                    'flex w-full items-start gap-3 rounded-2xl border px-3.5 py-3 text-left transition-all duration-200',
                    isActive
                      ? 'border-blue-200 bg-blue-50/70 shadow-sm'
                      : 'border-transparent bg-slate-50/80 hover:border-slate-200 hover:bg-white'
                  )}
                >
                  <div
                    className={cn(
                      'mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl',
                      isActive ? 'bg-blue-100 text-blue-600' : 'bg-white text-slate-500'
                    )}
                  >
                    {model.icon}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-slate-900">{model.label}</p>
                      <span
                        className={cn(
                          'rounded-full px-2 py-0.5 text-[11px] font-medium',
                          isActive ? 'bg-blue-100 text-blue-700' : 'bg-slate-200/80 text-slate-600'
                        )}
                      >
                        {model.badge}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-slate-700">{model.description}</p>
                    <p className="mt-1 text-xs leading-5 text-slate-500">{model.detail}</p>
                  </div>

                  <div
                    className={cn(
                      'mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border',
                      isActive
                        ? 'border-blue-500 bg-blue-500 text-white'
                        : 'border-slate-300 bg-white text-transparent'
                    )}
                  >
                    <Check className="h-3.5 w-3.5" />
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default ChatModelPicker;
