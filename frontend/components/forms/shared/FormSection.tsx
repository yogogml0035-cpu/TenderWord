'use client';

import React from 'react';
import { cn } from '@/lib/utils';

export interface FormSectionProps {
  /** Section title */
  title: string;
  /** Section content */
  children: React.ReactNode;
  /** Section index number (optional, for displaying badge) */
  index?: number;
  /** Additional CSS classes */
  className?: string;
  /** Optional badge text (e.g., "必填", "可选") */
  badge?: string;
  /** Badge variant */
  badgeVariant?: 'default' | 'required' | 'optional';
}

/**
 * FormSection - 统一章节卡片组件
 * 
 * Based on XJCG's clean style:
 * - White background card
 * - Rounded corners
 * - Optional index badge
 * - Clean, minimal design
 */
export function FormSection({
  title,
  children,
  index,
  className,
  badge,
  badgeVariant = 'default',
}: FormSectionProps) {
  const badgeStyles = {
    default: 'bg-[var(--secondary-bg)] text-[var(--text-muted)]',
    required: 'bg-red-100 text-red-700',
    optional: 'bg-amber-100 text-amber-700',
  };

  return (
    <div className={cn('card', className)}>
      <div className="mb-4 flex items-center gap-3">
        {index !== undefined && (
          <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-[var(--primary)] text-sm font-bold text-white">
            {index}
          </div>
        )}
        <h3 className="text-lg font-semibold text-[var(--foreground)]">
          {title}
        </h3>
        {badge && (
          <span
            className={cn(
              'rounded-full px-2 py-0.5 text-xs font-medium',
              badgeStyles[badgeVariant]
            )}
          >
            {badge}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

export default FormSection;
