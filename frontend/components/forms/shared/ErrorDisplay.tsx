'use client';

import React from 'react';
import { AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface ErrorDisplayProps {
  /** Error message(s) to display */
  message: string | string[];
  /** Additional CSS classes */
  className?: string;
  /** Error variant style */
  variant?: 'default' | 'inline' | 'banner';
  /** Whether to show icon */
  showIcon?: boolean;
  /** Callback when error is dismissed (shows close button when provided) */
  onDismiss?: () => void;
}

/**
 * ErrorDisplay - 统一错误提示组件
 * 
 * Displays error messages with consistent styling:
 * - AlertCircle icon
 * - Red background/border
 * - Support for single or multiple error messages
 * 
 * Based on XJCG form error display patterns.
 */
export function ErrorDisplay({
  message,
  className,
  variant = 'default',
  showIcon = true,
  onDismiss,
}: ErrorDisplayProps) {
  const messages = Array.isArray(message) ? message : [message];

  if (messages.length === 0 || messages.every((m) => !m)) {
    return null;
  }

  const variantStyles = {
    default: 'rounded-lg border border-red-200 bg-red-50 p-4',
    inline: 'rounded-md bg-red-50 px-3 py-2 text-sm',
    banner: 'rounded-xl border border-red-200 bg-red-50 p-4 animate-pulse',
  };

  const iconContainerStyles = {
    default: '',
    inline: 'h-4 w-4',
    banner: 'flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-red-100',
  };

  const iconStyles = {
    default: 'h-5 w-5 text-[var(--error)]',
    inline: 'h-4 w-4 text-red-600',
    banner: 'h-5 w-5 text-red-600',
  };

  const textStyles = {
    default: 'text-sm text-[var(--error)]',
    inline: 'text-sm text-red-700',
    banner: 'text-sm font-medium text-red-700',
  };

  return (
    <div
      className={cn(
        'flex items-start gap-2',
        variantStyles[variant],
        className
      )}
      role="alert"
    >
      {showIcon && (
        <div className={cn('flex-shrink-0', iconContainerStyles[variant])}>
          <AlertCircle className={iconStyles[variant]} />
        </div>
      )}

      <div className="flex-1">
        {messages.length === 1 ? (
          <p className={textStyles[variant]}>{messages[0]}</p>
        ) : (
          <ul className={cn('list-inside list-disc space-y-1', textStyles[variant])}>
            {messages.map((msg, index) => (
              msg && <li key={index}>{msg}</li>
            ))}
          </ul>
        )}
      </div>

      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="flex-shrink-0 text-red-400 hover:text-red-600"
          aria-label="Dismiss error"
        >
          <svg
            className="h-4 w-4"
            width={16}
            height={16}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      )}
    </div>
  );
}

export default ErrorDisplay;
