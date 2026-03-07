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
    required: 'bg-red-100/90 text-red-700',
    optional: 'bg-amber-100/90 text-amber-700',
  };

  return (
    <div
      className={cn(
        'rounded-xl border border-[var(--border)]/80 bg-white px-5 py-4 shadow-[0_8px_22px_rgba(15,23,42,0.06)]',
        className
      )}
    >
      <div className="mb-3.5 flex items-center gap-2.5">
        {index !== undefined && (
          <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md bg-[var(--primary)] text-sm font-semibold text-white">
            {index}
          </div>
        )}
        <h3 className="text-[17px] font-semibold text-[var(--foreground)]">
          {title}
        </h3>
        {badge && (
          <span
            className={cn(
              'rounded-full px-2 py-0.5 text-[11px] font-semibold',
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
